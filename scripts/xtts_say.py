import sys, torch
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig
torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig, XttsArgs, BaseDatasetConfig])

from TTS.api import TTS

text = " ".join(sys.argv[1:]) or "Hello from XTTS v2."
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
tts.tts_to_file(
    text=text,
    file_path="/home/USER/xtts_out.wav",
    speaker_wav="/home/USER/revy_ref.wav",
    language="en",
)
print("Wrote /home/USER/xtts_out.wav")
