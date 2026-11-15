# Round trip: Piper -> faster-whisper (stt-turbo)

- Date: 2026-11-15 16:23 UTC
- Machine: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz, 8 threads for speech to text
- Speech to text: `stt-turbo` @ `0a363e9161cb`, compute type int8, beam 5, language `ar`, faster-whisper 1.2.1, ctranslate2 4.9.0
- Text to speech: `tts-ar-kareem-medium` @ `6b9cfaacb4fb`, piper-tts 1.8.0, onnxruntime 1.32.0
- Synthetic audio from one voice: this checks the pipeline and its speed, not recognition quality.

| Id | CER | WER | Audio s | TTS s | STT s | Reference | Heard |
|---|---|---|---|---|---|---|---|
| R01 | 0.0% | 0.0% | 3.77 | 0.47 | 13.32 | مرحبا، كيف يمكنني مساعدتك اليوم؟ | مرحباً، كيف يمكنني مساعدتك اليوم؟ |
| R02 | 0.0% | 0.0% | 3.24 | 0.17 | 10.63 | ما هي عاصمة مملكة البحرين؟ | ما هي عاصمة مملكة البحرين؟ |
| R03 | 0.0% | 0.0% | 4.31 | 0.24 | 10.07 | أريد أن أعرف حالة الطقس غدا في المنامة. | أريد أن أعرف حالة الطقس غداً في المنامة. |
| R04 | 0.0% | 0.0% | 4.06 | 0.22 | 9.45 | متى يفتح المصرف أبوابه يوم الأحد؟ | متى يفتح المصرف أبوابه يوم الأحد؟ |
| R05 | 0.0% | 0.0% | 4.62 | 0.23 | 8.69 | ذكرني بالاجتماع في الساعة الخامسة مساء. | ذكرني بالاجتماع في الساعة الخامسة مساء |
| R06 | 0.0% | 0.0% | 3.47 | 0.17 | 8.66 | كم يبعد المطار عن وسط المدينة؟ | كم يبعد المطار عن وسط المدينة؟ |
| R07 | 0.0% | 0.0% | 4.05 | 0.19 | 9.03 | شكرا لك، هذا كل ما أحتاجه الآن. | شكرا لك هذا كل ما أحتاجه الآن. |
| R08 | 0.0% | 0.0% | 4.06 | 0.21 | 9.36 | هل يمكنك أن تعيد الجملة الأخيرة ببطء؟ | هل يمكنك أن تعيد الجملة الأخيرة ببطء؟ |

- sentences 8, audio 31.6 s, corpus CER 0.0%, corpus WER 0.0%
- speech to text: median 9.40 s, slowest 13.32 s per sentence, RTF 2.51
- text to speech: RTF 0.06
- OK: corpus CER 0.0% <= 10%
- OK: corpus WER 0.0% <= 20%
- OK: worst sentence R01 CER 0.0% <= 30%
- OK: 2 s of silence -> '' (must be empty)

**PASSED**
