# How the services stop (M5, D31)

## M4 images, Docker's default 10 s grace period (2026-11-16 22:16 UTC)

| Container | SIGTERM to exit, s | Exit code |
|---|---|---|
| voice-gateway | 2.6 | 0 |
| voice-stt | 4.1 | 137 |
| voice-tts | 4.3 | 137 |
| voice-ollama | 1.7 | 0 |

`voice-gateway`:
```
22:16:43.709 INFO:     Shutting down
22:16:43.811 INFO:     Waiting for application shutdown.
22:16:43.812 INFO:     Application shutdown complete.
22:16:43.819 INFO:     Finished server process [1]
```

`voice-stt`:
```
22:16:46.348 INFO:     Shutting down
22:16:46.449 INFO:     Waiting for application shutdown.
22:16:47.091 INFO:     Application shutdown complete.
22:16:47.091 INFO:     Finished server process [1]
```

`voice-tts`:
```
22:16:46.507 INFO:     Shutting down
22:16:46.698 INFO:     Waiting for application shutdown.
22:16:47.758 INFO:     Application shutdown complete.
22:16:47.930 INFO:     Finished server process [1]
```

## M5 images, 45 s grace period, uvicorn drains for up to 30 s (2026-11-16 22:47 UTC)

| Container | SIGTERM to exit, s | Exit code |
|---|---|---|
| voice-gateway | 0.6 | 0 |
| voice-stt | 1.0 | 0 |
| voice-tts | 0.7 | 0 |
| voice-ollama | 0.6 | 0 |

`voice-gateway`:
```
22:47:31.025 INFO:     Shutting down
22:47:31.127 INFO:     Waiting for application shutdown.
22:47:31.127 INFO:     Application shutdown complete.
22:47:31.127 INFO:     Finished server process [1]
```

`voice-stt`:
```
22:47:31.688 INFO:     Shutting down
22:47:31.789 INFO:     Waiting for application shutdown.
22:47:31.824 INFO:     Application shutdown complete.
22:47:31.824 INFO:     Finished server process [1]
```

`voice-tts`:
```
22:47:31.749 INFO:     Shutting down
22:47:31.849 INFO:     Waiting for application shutdown.
22:47:31.870 INFO:     Application shutdown complete.
22:47:31.870 INFO:     Finished server process [1]
```

