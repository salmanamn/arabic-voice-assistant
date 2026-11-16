# Round trip: Piper -> faster-whisper (stt-small)

- Date: 2026-11-15 18:10 UTC
- Machine: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz, 6 threads for speech to text
- Speech to text: `stt-small` @ `536b0662742c`, compute type int8, beam 5, language `ar`, faster-whisper 1.2.1, ctranslate2 4.9.0
- Text to speech: `tts-ar-kareem-medium` @ `6b9cfaacb4fb`, piper-tts 1.8.0, onnxruntime 1.32.0
- Synthetic audio from one voice: this checks the pipeline and its speed, not recognition quality.

| Id | CER | WER | Audio s | TTS s | STT s | Reference | Heard |
|---|---|---|---|---|---|---|---|
| R01 | 0.0% | 0.0% | 3.77 | 0.44 | 2.51 | مرحبا، كيف يمكنني مساعدتك اليوم؟ | مرحبا كيف يمكنني مساعدتك اليوم؟ |
| R02 | 0.0% | 0.0% | 3.24 | 0.24 | 2.33 | ما هي عاصمة مملكة البحرين؟ | ما هي عاصمة مملكة البحرين؟ |
| R03 | 0.0% | 0.0% | 4.31 | 0.26 | 2.69 | أريد أن أعرف حالة الطقس غدا في المنامة. | أريد أن أعرف حالة الطقس غدا في المنامة |
| R04 | 0.0% | 0.0% | 4.06 | 0.21 | 1.93 | متى يفتح المصرف أبوابه يوم الأحد؟ | متى يفتح المصرف أبوابه يوم الأحد؟ |
| R05 | 3.0% | 16.7% | 4.62 | 0.19 | 1.95 | ذكرني بالاجتماع في الساعة الخامسة مساء. | ذكرني بالجتماع في الساعة الخامسة مساء |
| R06 | 0.0% | 0.0% | 3.47 | 0.14 | 1.62 | كم يبعد المطار عن وسط المدينة؟ | كم يبعد المطار عن وسط المدينة؟ |
| R07 | 0.0% | 0.0% | 4.05 | 0.16 | 1.58 | شكرا لك، هذا كل ما أحتاجه الآن. | شكرا لك هذا كل ما أحتاجه الآن |
| R08 | 3.3% | 14.3% | 4.06 | 0.18 | 1.91 | هل يمكنك أن تعيد الجملة الأخيرة ببطء؟ | هل يمكنك أن تعيد الجملة الأخيرة ببط؟ |

- sentences 8, audio 31.6 s, corpus CER 0.9%, corpus WER 4.0%
- speech to text: median 1.94 s, slowest 2.69 s per sentence, RTF 0.52
- text to speech: RTF 0.06
- OK: corpus CER 0.9% <= 10%
- OK: corpus WER 4.0% <= 20%
- OK: worst sentence R08 CER 3.3% <= 30%
- OK: 2 s of silence -> '' (must be empty)

**PASSED**
