"""
Script táº£i mÃ´ hÃ¬nh ASR Sherpa-ONNX Zipformer 30M tá»± Ä‘á»™ng
=========================================================
Táº£i trá»ng sá»‘ pre-trained ONNX Zipformer (30M parameters) siÃªu nháº¹ tá»« release cá»§a k2-fsa/sherpa-onnx.
"""

import os
import sys
import urllib.request
import tarfile
import zipfile

MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-en-2023-06-26.tar.bz2"
TARGET_DIR = os.path.join(os.path.dirname(__file__), "models", "sherpa-onnx-zipformer-30M")

def download_and_extract_model(url=MODEL_URL, target_dir=TARGET_DIR):
    os.makedirs(target_dir, exist_ok=True)
    archive_name = os.path.basename(url)
    archive_path = os.path.join(target_dir, archive_name)

    print(f"ðŸš€ Äang táº£i mÃ´ hÃ¬nh Sherpa-ONNX Zipformer 30M tá»«:\n   {url}")
    
    def progress_hook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = (downloaded / total_size) * 100
            sys.stdout.write(f"\r progress: {percent:.1f}% [{downloaded / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB]")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, archive_path, reporthook=progress_hook)
        print("\nâœ… Táº£i thÃ nh cÃ´ng! Äang giáº£i nÃ©n mÃ´ hÃ¬nh...")
        
        if archive_path.endswith(".tar.bz2") or archive_path.endswith(".tar.gz"):
            with tarfile.open(archive_path, "r:*") as tar:
                tar.extractall(path=target_dir)
        elif archive_path.endswith(".zip"):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
                
        print(f"ðŸŽ‰ MÃ´ hÃ¬nh Zipformer 30M Ä‘Ã£ sáºµn sÃ ng táº¡i: {target_dir}")
    except Exception as e:
        print(f"\nâŒ Lá»—i khi táº£i mÃ´ hÃ¬nh: {e}")

if __name__ == "__main__":
    download_and_extract_model()


"""
ASR Speech-to-Text Module using Sherpa-ONNX Zipformer 30M
==========================================================
Provides lightweight, ultra-fast speech recognition for video audio streams.
Uses Next-gen Kaldi Zipformer ONNX models (~30M parameters) running on ONNX Runtime.
"""

import os
import sys
import glob
import json
import wave
import numpy as np
from typing import List, Dict, Any, Optional

try:
    import sherpa_onnx
    SHERPA_AVAILABLE = True
except ImportError:
    SHERPA_AVAILABLE = False

try:
    import av
    AV_AVAILABLE = True
except ImportError:
    AV_AVAILABLE = False


class SherpaZipformerASR:
    """
    ASR Recognizer based on Sherpa-ONNX Zipformer (30M lightweight model).
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        tokens_path: Optional[str] = None,
        encoder_path: Optional[str] = None,
        decoder_path: Optional[str] = None,
        joiner_path: Optional[str] = None,
        num_threads: int = 4
    ):
        self.num_threads = num_threads
        self.recognizer = None
        self.is_ready = False

        if not SHERPA_AVAILABLE:
            print("âš ï¸ sherpa_onnx chÆ°a Ä‘Æ°á»£c cÃ i Ä‘áº·t. Vui lÃ²ng cÃ i: pip install sherpa-onnx")
            return

        # Default model search paths
        base_dir = model_dir or os.path.join(os.path.dirname(__file__), "models", "sherpa-onnx-zipformer-30M")
        
        encoder = encoder_path or os.path.join(base_dir, "encoder-epoch-99-avg-1.onnx")
        decoder = decoder_path or os.path.join(base_dir, "decoder-epoch-99-avg-1.onnx")
        joiner = joiner_path or os.path.join(base_dir, "joiner-epoch-99-avg-1.onnx")
        tokens = tokens_path or os.path.join(base_dir, "tokens.txt")

        # Fallback check for any .onnx files in base_dir
        if os.path.exists(base_dir):
            onnx_files = glob.glob(os.path.join(base_dir, "*.onnx"))
            for f in onnx_files:
                if "encoder" in f.lower(): encoder = f
                elif "decoder" in f.lower(): decoder = f
                elif "joiner" in f.lower(): joiner = f
            token_files = glob.glob(os.path.join(base_dir, "*tokens*.txt"))
            if token_files: tokens = token_files[0]

        if os.path.exists(encoder) and os.path.exists(tokens):
            try:
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=encoder,
                    decoder=decoder if os.path.exists(decoder) else "",
                    joiner=joiner if os.path.exists(joiner) else "",
                    tokens=tokens,
                    num_threads=self.num_threads,
                    sample_rate=16000,
                    feature_dim=80,
                    decoding_method="greedy_search"
                )
                self.is_ready = True
                print(f"âœ… ÄÃ£ khá»Ÿi táº¡o Sherpa-ONNX Zipformer 30M ASR thÃ nh cÃ´ng: {encoder}")
            except Exception as e:
                print(f"âš ï¸ Lá»—i khá»Ÿi táº¡o Sherpa-ONNX Zipformer: {e}")
        else:
            print(f"â„¹ï¸ ChÆ°a tÃ¬m tháº¥y trá»ng sá»‘ model Zipformer 30M táº¡i '{base_dir}'. Vui lÃ²ng táº£i model ONNX Zipformer.")

    def extract_audio_pcm(self, video_path: str, target_sample_rate: int = 16000) -> Optional[np.ndarray]:
        """
        TrÃ­ch xuáº¥t dá»¯ liá»‡u Ã¢m thanh dáº¡ng PCM 16kHz mono tá»« video MP4/MKV.
        """
        if not AV_AVAILABLE:
            print("âš ï¸ PyAV chÆ°a Ä‘Æ°á»£c cÃ i Ä‘áº·t. KhÃ´ng thá»ƒ giáº£i mÃ£ audio trá»±c tiáº¿p tá»« video.")
            return None

        try:
            container = av.open(video_path)
            audio_stream = next((s for s in container.streams if s.type == 'audio'), None)
            if not audio_stream:
                return None

            resampler = av.AudioResampler(
                format='s16',
                layout='mono',
                rate=target_sample_rate
            )

            samples = []
            for frame in container.decode(audio_stream):
                resampled_frames = resampler.resample(frame)
                for r_frame in resampled_frames:
                    arr = r_frame.to_ndarray()
                    samples.append(arr)

            if not samples:
                return None

            audio_data = np.concatenate(samples, axis=1).squeeze()
            # Normalize to float32 in [-1.0, 1.0]
            float_samples = audio_data.astype(np.float32) / 32768.0
            return float_samples
        except Exception as e:
            print(f"âš ï¸ Lá»—i trÃ­ch xuáº¥t audio tá»« {video_path}: {e}")
            return None

    def transcribe_video(self, video_path: str) -> Dict[str, Any]:
        """
        Cháº¡y nháº­n dáº¡ng giá»ng nÃ³i ASR trÃªn file video.
        """
        if not self.is_ready:
            return {"text": "", "error": "Sherpa Zipformer Model not ready"}

        samples = self.extract_audio_pcm(video_path, target_sample_rate=16000)
        if samples is None or len(samples) == 0:
            return {"text": "", "error": "No audio stream extracted"}

        try:
            stream = self.recognizer.create_stream()
            stream.accept_waveform(16000, samples)
            self.recognizer.decode_stream(stream)
            text = stream.result.text.strip()

            return {
                "text": text,
                "duration_sec": len(samples) / 16000.0,
                "status": "success"
            }
        except Exception as e:
            return {"text": "", "error": str(e)}


def test_asr_on_video(video_path: str):
    """
    HÃ m test máº«u cháº¡y ASR Zipformer 30M trÃªn 1 file video.
    """
    print(f"\nðŸŽ™ï¸ --- CHáº Y THá»¬ MÃ” HÃŒNH ASR SHERPA ZIPFORMER 30M ---")
    print(f"File video: {video_path}")
    
    engine = SherpaZipformerASR()
    if not engine.is_ready:
        print("ðŸ’¡ HÆ°á»›ng dáº«n: Táº£i trá»ng sá»‘ Zipformer 30M (ONNX) Ä‘áº·t vÃ o thÆ° má»¥c backend/models/sherpa-onnx-zipformer-30M/")
        return

    res = engine.transcribe_video(video_path)
    print(f"Káº¿t quáº£ ASR: {json.dumps(res, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_asr_on_video(sys.argv[1])
    else:
        print("Sá»­ dá»¥ng: python asr_sherpa.py <path_to_video.mp4>")

