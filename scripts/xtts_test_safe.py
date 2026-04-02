import torch

from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
from TTS.config.shared_configs import BaseDatasetConfig

torch.serialization.add_safe_globals([
    XttsConfig,
    XttsAudioConfig,
    XttsArgs,
    BaseDatasetConfig,
])

from TTS.api import TTS

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
tts.tts_to_file(
    text="This is an XTTS v2 cloning test running locally on GPU.",
    file_path="/home/USER/xtts_out.wav",
    speaker_wav="/home/USER/revy_ref.wav",
    language="en",
)
print("Wrote /home/USER/xtts_out.wav")
