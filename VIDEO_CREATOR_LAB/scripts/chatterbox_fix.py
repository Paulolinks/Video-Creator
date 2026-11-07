"""Fixes and a faster generation loop for the Chatterbox Multilingual runtime. The Video Cutter's install stays
untouched: everything here runs inside our own process, on top of the installed package.

Defects found in the installed chatterbox 0.1.6 (models/t3/inference/alignment_stream_analyzer.py, models/t3/t3.py):
1. Cut-offs: the hallucination guard forces the end of speech when only 2 identical speech tokens come in a row
   (its own comment says 3; sustained sounds and short pauses repeat tokens normally), so sentences get cut short.
   Now it only stops on a real loop (STUCK_RUN identical tokens, about half a second of the same sound).
2. Babble ("another language"): the guard forbids stopping until the attention reaches the end of the text. When
   the alignment gets lost, the model is forced to keep talking and invents sounds. Now there is a length ceiling
   from the text size, and the take reports it, so the caller can redo it.
3. Slowdown over a batch: every take registers 3 more attention hooks on the transformer and never removes them,
   so a run with hundreds of sentences gets slower and slower. Our loop uses one fixed set of hooks.
4. Slow steps: each speech token costs about 65 ms, almost all of it Python/kernel-launch overhead (thousands of
   tiny GPU calls per step). Our loop keeps the attention memory in fixed buffers (StaticCache) and records the
   whole transformer step once as a CUDA graph, then replays it; and only the 3 layers the guard reads return
   attention maps (the other 27 keep the fast kernel). Falls back to the plain loop if graph capture fails.
5. Cleaner voice reference: the model only listens to the first 6 s (speaking style) and 10 s (timbre) of the
   reference. Long pauses there waste that window, so a condensed copy with short pauses can be used instead.
"""
import hashlib
import logging
import subprocess
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import StaticCache
from transformers.generation.logits_process import MinPLogitsWarper, RepetitionPenaltyLogitsProcessor, TopPLogitsWarper

from chatterbox.models.t3.inference import alignment_stream_analyzer as asa
from chatterbox.models.t3.modules.cond_enc import T3Cond
from chatterbox.models.s3tokenizer import drop_invalid_tokens
from chatterbox.mtl_tts import punc_norm

STUCK_RUN = 12          # identical speech tokens in a row (25 per second) before calling it a loop
FRAMES_PER_TOKEN = 4.0  # ceiling of speech frames per text token (measured: normal speech 1.7-3.5, babble 7)
SLACK_FRAMES = 40       # plus 1.6 s for every take: short lines (questions) are spoken slower, with longer ends
MAX_LEN = 1800          # fixed attention memory: conditioning (~152) + text + speech tokens
MAX_NEW = 1000          # same ceiling the package uses

logging.getLogger("chatterbox.models.t3.inference.alignment_stream_analyzer").setLevel(logging.ERROR)
logging.getLogger("transformers.models.llama.modeling_llama").setLevel(logging.ERROR)


class Guarda:
    """The package's alignment guard (same heuristics), with the fixes 1 and 2 above and no hooks of its own."""

    def __init__(self, i, j, eos_idx):
        self.text_tokens_slice = (i, j)
        self.eos_idx = eos_idx
        self.alignment = torch.zeros(0, j - i)
        self.curr_frame_pos = 0
        self.text_position = 0
        self.started, self.started_at = False, None
        self.complete, self.completed_at = False, None
        self.run, self.last_tok, self.reason = 0, None, None

    def step(self, aligned_attn, logits, last_token):
        """aligned_attn: mean attention of the spied heads, (rows, >= j) on the CPU."""
        i, j = self.text_tokens_slice
        A_chunk = (aligned_attn[j:, i:j] if self.curr_frame_pos == 0 else aligned_attn[:, i:j]).clone()
        A_chunk[:, self.curr_frame_pos + 1:] = 0
        self.alignment = torch.cat((self.alignment, A_chunk), dim=0)
        A = self.alignment
        T, S = A.shape
        cur = A_chunk[-1].argmax()
        if -4 < cur - self.text_position < 7:
            self.text_position = cur
        false_start = (not self.started) and (A[-2:, -2:].max() > 0.1 or A[:, :4].max() < 0.5)
        self.started = not false_start
        if self.started and self.started_at is None:
            self.started_at = T
        self.complete = self.complete or self.text_position >= S - 3
        if self.complete and self.completed_at is None:
            self.completed_at = T
        long_tail = self.complete and (A[self.completed_at:, -3:].sum(dim=0).max() >= 5)
        repetition = self.complete and (A[self.completed_at:, :-5].max(dim=1).values.sum() > 5)
        if last_token is not None:
            self.run = self.run + 1 if last_token == self.last_tok else 1
            self.last_tok = last_token
        stuck = self.run >= STUCK_RUN
        too_long = self.curr_frame_pos >= int(FRAMES_PER_TOKEN * S) + SLACK_FRAMES
        if cur < S - 3 and S > 5 and not too_long:
            logits[..., self.eos_idx] = -2**15  # not at the end of the text yet: keep talking
        reason = ("fim_longo" if long_tail else "repeticao" if repetition else "travou" if stuck
                  else "longa_demais" if too_long else None)
        if reason:
            self.reason = self.reason or reason
            logits = -(2**15) * torch.ones_like(logits)
            logits[..., self.eos_idx] = 2**15
        self.curr_frame_pos += 1
        return logits


class Gerador:
    """Speech-token generation for one loaded model: fixed attention memory, 3 spied layers, CUDA-graph step."""

    def __init__(self, model, usar_grafo=True):
        self.t3 = model.t3
        self.tfmr = model.t3.tfmr
        self.device = model.device
        self.heads = asa.LLAMA_ALIGNED_HEADS
        self.attn = {}
        for k, (layer_idx, _) in enumerate(self.heads):
            att = self.tfmr.layers[layer_idx].self_attn
            att._forward_hooks.clear()  # drop hooks left by the package's own guard
            orig = att.forward

            def forward(*a, _orig=orig, **kw):  # only these 3 layers return attention maps
                kw["output_attentions"] = True
                return _orig(*a, **kw)
            att.forward = forward
            att.register_forward_hook(lambda m, i, o, k=k: self.attn.__setitem__(k, o[1]))
        self.tfmr.config.output_attentions = False
        dtype = next(self.tfmr.parameters()).dtype
        self.cache = StaticCache(config=self.tfmr.config, batch_size=2, max_cache_len=MAX_LEN, device=self.device,
                                 dtype=dtype)
        self.inp = torch.zeros(2, 1, self.tfmr.config.hidden_size, device=self.device, dtype=dtype)
        self.pos = torch.zeros(1, dtype=torch.long, device=self.device)
        self.usar_grafo = usar_grafo and str(self.device).startswith("cuda")
        self.grafo = None
        self.modo = "grafo" if self.usar_grafo else "normal"

    def _passo(self):
        out = self.tfmr(inputs_embeds=self.inp, past_key_values=self.cache, cache_position=self.pos, use_cache=True,
                        output_attentions=False, output_hidden_states=False, return_dict=True)
        self.logits = self.t3.speech_head(out.last_hidden_state)
        self.spied = [self.attn[k][0, h] for k, (_, h) in enumerate(self.heads)]  # each (1, MAX_LEN)

    def _capturar(self):
        try:
            s = torch.cuda.Stream()
            s.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(s):
                for _ in range(2):
                    self._passo()
            torch.cuda.current_stream().wait_stream(s)
            g = torch.cuda.CUDAGraph()
            with torch.cuda.graph(g):
                self._passo()
            self.grafo = g
        except Exception as e:  # noqa: BLE001 - any capture problem: keep the plain loop
            print(f"  (modo rápido indisponível, seguindo no normal: {type(e).__name__}: {e})", flush=True)
            self.usar_grafo, self.grafo, self.modo = False, None, "normal"

    def gerar_tokens(self, t3_cond, text_tokens, temperature, cfg_weight, repetition_penalty, min_p, top_p):
        t3, hp = self.t3, self.t3.hp
        bos = torch.tensor([[hp.start_speech_token]], dtype=torch.long, device=self.device)
        embeds, len_cond = t3.prepare_input_embeds(t3_cond=t3_cond, text_tokens=text_tokens,
                                                   speech_tokens=hp.start_speech_token * torch.ones_like(text_tokens[:, :1]),
                                                   cfg_weight=cfg_weight)
        bos_embed = t3.speech_emb(bos) + t3.speech_pos_emb.get_fixed_embedding(0)
        x = torch.cat([embeds, torch.cat([bos_embed, bos_embed])], dim=1)
        L = x.size(1)
        guard = Guarda(len_cond, len_cond + text_tokens.size(-1), hp.stop_speech_token)
        # whole prompt at once (all layers, full causal mask), writing positions 0..L-1 of the fixed memory
        out = self.tfmr(inputs_embeds=x, past_key_values=self.cache, cache_position=torch.arange(L, device=self.device),
                        use_cache=True, output_attentions=False, output_hidden_states=False, return_dict=True)
        # (the fixed memory always gets an explicit causal mask, so the fast kernel is safe here too; only the
        # 3 spied layers return attention maps, through the hooks)
        logits_all = t3.speech_head(out.last_hidden_state[:, -1:, :])
        j = len_cond + text_tokens.size(-1)
        att = torch.stack([self.attn[k][0, h, :, :j] for k, (_, h) in enumerate(self.heads)]).mean(0).cpu()
        del out
        self.attn.clear()
        if self.usar_grafo and self.grafo is None:
            self.pos.fill_(L)
            self._capturar()
        rep = RepetitionPenaltyLogitsProcessor(penalty=float(repetition_penalty))
        minp = MinPLogitsWarper(min_p=min_p)
        topp = TopPLogitsWarper(top_p=top_p) if top_p < 1.0 else None
        ids = bos.clone()
        predicted = []
        max_new = min(MAX_NEW, MAX_LEN - L - 1)
        for i in range(max_new):
            step_logits = logits_all[:, -1, :]
            cond, uncond = step_logits[0:1], step_logits[1:2]
            logits = cond + cfg_weight * (cond - uncond)
            last = ids[0, -1].item() if i > 0 else None
            logits = guard.step(att, logits.clone(), last)
            logits = rep(ids, logits)
            if temperature != 1.0:
                logits = logits / temperature
            logits = minp(ids, logits)
            if topp is not None:
                logits = topp(ids, logits)
            nxt = torch.multinomial(torch.softmax(logits, dim=-1), num_samples=1)
            predicted.append(nxt)
            ids = torch.cat([ids, nxt], dim=1)
            if nxt.item() == hp.stop_speech_token:
                break
            e = t3.speech_emb(nxt) + t3.speech_pos_emb.get_fixed_embedding(i + 1)
            self.inp.copy_(torch.cat([e, e]))
            self.pos.fill_(L + i)
            if self.grafo is not None:
                self.grafo.replay()
            else:
                self._passo()
            logits_all = self.logits
            att = torch.stack([a[:, :j] for a in self.spied]).mean(0).cpu()
        tokens = torch.cat(predicted, dim=1)
        del logits_all, logits, att
        info = {"fim": guard.reason or "natural", "frames": int(tokens.numel()), "texto_tokens": int(text_tokens.size(-1)),
                "completa": bool(guard.complete)}
        return tokens[0], info


_GERADORES = {}


def gerar(model, text, lang, exaggeration=0.4, cfg_weight=0.5, temperature=0.8, repetition_penalty=2.0,
          min_p=0.05, top_p=1.0):
    """Like model.generate (same steps and defaults), faster and with a report of how the take ended.
    Returns (wav tensor (1, n), info)."""
    ger = _GERADORES.get(id(model))
    if ger is None:
        ger = _GERADORES[id(model)] = Gerador(model)
    if float(exaggeration) != float(model.conds.t3.emotion_adv[0, 0, 0].item()):
        c = model.conds.t3
        model.conds.t3 = T3Cond(speaker_emb=c.speaker_emb, cond_prompt_speech_tokens=c.cond_prompt_speech_tokens,
                                emotion_adv=exaggeration * torch.ones(1, 1, 1)).to(device=model.device)
    tokens = model.tokenizer.text_to_tokens(punc_norm(text), language_id=lang.lower()).to(model.device)
    tokens = torch.cat([tokens, tokens], dim=0)  # two rows for classifier-free guidance
    tokens = F.pad(F.pad(tokens, (1, 0), value=model.t3.hp.start_text_token), (0, 1),
                   value=model.t3.hp.stop_text_token)
    with torch.inference_mode():
        speech, info = ger.gerar_tokens(model.conds.t3, tokens, temperature, cfg_weight, repetition_penalty, min_p, top_p)
        info["modo"] = ger.modo
        speech = drop_invalid_tokens(speech).to(model.device)
        wav, _ = model.s3gen.inference(speech_tokens=speech, ref_dict=model.conds.gen)
        wav = wav.squeeze(0).detach().cpu().numpy()
        wav = model.watermarker.apply_watermark(wav, sample_rate=model.sr)
    if str(model.device).startswith("cuda"):
        info["vram_mb"] = round(torch.cuda.memory_reserved() / 2**20)
        torch.cuda.empty_cache()  # prompts vary in length: return the odd-sized blocks so memory does not creep up
    return torch.from_numpy(wav).unsqueeze(0), info


def aplicar(model):
    """Kept for callers: the fixes are installed lazily by gerar()."""
    return model


REF_VERSAO = "limpa1"


def referencia_limpa(ref, cache_dir):
    """A copy of the voice reference with pauses shortened to 0.25 s and the level evened out, so the 6 s / 10 s
    the model listens to are full of speech. Made once per recording (cached by size/date)."""
    ref = Path(ref)
    st = ref.stat()
    key = hashlib.sha1(f"{ref.resolve()}|{st.st_size}|{st.st_mtime}|{REF_VERSAO}".encode()).hexdigest()[:12]
    out = Path(cache_dir) / f"{ref.parent.name}_{key}.wav"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        flt = ("highpass=f=60,"
               "silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.05:"
               "stop_periods=-1:stop_duration=0.25:stop_threshold=-42dB,"
               "loudnorm=I=-20:TP=-2:LRA=11")
        tmp = out.with_suffix(".tmp.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(ref), "-af", flt, "-ar", "24000", "-ac", "1",
                        str(tmp)], check=True)
        tmp.replace(out)
    return out
