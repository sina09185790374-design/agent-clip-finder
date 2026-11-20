# agent-clip-finder demo transcript

The demo synthesizes a 24 s recording (quiet talk, two shouts) plus a
matching SRT, then runs the whole pipeline. The WAV is generated, not
shipped (`demo` writes it); `demo.srt` is the transcript used.

```
$ python3 -m agent_clip_finder demo --out /tmp/clip-demo
demo files in /tmp/clip-demo
moments found: 2
  moment-1: 8.0s-11.0s score=9.3 title='Wow, oh my god, look at this!'
  moment-2: 18.0s-20.5s score=9.3 title='No way, that was insane!'
demo plan PASSED the gate
```

The plan for the same run (`plan demo.wav --srt demo.srt --min 2 --max 10`):

```json
{
  "source": "demo.wav",
  "duration": 24.0,
  "min_s": 2.0,
  "max_s": 10.0,
  "clips": [
    {
      "id": "moment-1",
      "start": 8.0,
      "end": 11.0,
      "length": 3.0,
      "score": 9.3,
      "title": "Wow, oh my god, look at this!",
      "hook": "Wow, oh my god, look at this!",
      "ffmpeg": "ffmpeg -ss 8.00 -to 11.00 -i \"demo.wav\" -vf \"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920\" -c:v libx264 -crf 18 -c:a aac \"moment-1.mp4\""
    },
    {
      "id": "moment-2",
      "start": 18.0,
      "end": 20.5,
      "length": 2.5,
      "score": 9.3,
      "title": "No way, that was insane!",
      "hook": "No way, that was insane!",
      "ffmpeg": "ffmpeg -ss 18.00 -to 20.50 -i \"demo.wav\" -vf \"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920\" -c:v libx264 -crf 18 -c:a aac \"moment-2.mp4\""
    }
  ]
}
```

Both clips snap exactly to their SRT cues (8.0–11.0 and 18.0–20.5);
the quiet stretches produce no moments at all.
```
