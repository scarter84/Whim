from TTS.api import TTS

tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
tts.tts_to_file(
    text="This is an XTTS v2 cloning test running locally on GPU.",
    file_path="xtts_out.wav",
    speaker_wav="/home/USER/revy_ref.wav",
    language="en",
)
print("Wrote xtts_out.wav")
