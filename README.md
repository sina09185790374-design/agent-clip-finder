# agent-clip-finder

Find the loudest, most quotable moments in a long recording — without
watching the whole video. A small stdlib-only CLI: feed it a WAV file and
an optional SRT transcript, and it scores every 100 ms window for sudden
loudness jumps, raised voices (2–4 kHz band energy) and excitement words,
picks the peaks, snaps them to sentence boundaries, and emits a 9:16 clip
plan (JSON + ffmpeg commands). It learns from your 1–5 star ratings: after
8 ratings the signal weights are refit toward your taste. No network, no
keys, no dependencies.

**Pattern** (original code; pattern only, learned from today's radar):
iamajmeena/neonclipping turns long YouTube/Twitch videos into captioned
9:16 clips audio-first: download audio only, take free word-timed captions,
score loudness jumps / raised voices / quiet-to-loud transitions against a
2-minute local baseline, let a local LLM score the moment and write a title
and hook, snap the edges to sentence boundaries, and only then download the
chosen video sections. It also learns from 5-star ratings (ridge regression
after 8 ratings) and clips live streams from chat spikes. This tool is that
idea as a small local Python CLI: `analyze` scores the audio, `plan` builds
the clip plan, `rate` teaches the weights, `weights` shows them, `check`
is the CI gate, and `demo` runs the whole pipeline on a synthetic
recording. The LLM judge is replaced by transcript keyword signals (EN +
FA) — the same scoring shape, no model needed.

## How it works

1. **Measure.** `analyze` reads the WAV (any PCM WAV, mixed down to mono)
   and measures RMS loudness, zero-crossing rate and 2–4 kHz band energy
   (Goertzel at 2.5/3.0/3.5 kHz, Hann-windowed) in 100 ms windows. The
   loudness baseline is local: each window is compared against the median
   RMS of the previous 120-second block, so a loud section late in a long
   recording is judged against what came before it.
2. **Score.** Each window gets `loud` (RMS vs local baseline, clipped at
   5×), `voice` (band energy vs the file median, clipped at 5×) and
   `words` (an excitement keyword in the transcript cue under the window:
   "wow", "oh my god", "no way" — or «وای»، «عجب»، «ایول»). One weighted
   sum, defaults `loud 1.0 / voice 0.7 / words 0.8`.
3. **Pick.** Peaks are the best windows at least 8 s apart that clearly
   beat the ordinary windows (halfway from the median score to the peak).
   Flat audio yields no moments. Each moment's span grows from its peak
   while neighbours keep at least half the peak's score.
4. **Plan.** `plan` snaps start/end to sentence boundaries from the SRT,
   enforces min/max clip length (default 30–80 s), drops lower-scored clips
   that overlap a kept clip, and writes a title + hook from the transcript
   under the peak plus a ready `ffmpeg` command per clip
   (1080×1920, libx264, CRF 18).
5. **Learn.** `rate --moment moment-1 --rating 5 --signals '{...}'`
   appends to `feedback.jsonl`. After 8 ratings, `weights` refits: each
   signal's weight moves toward the mean rating of the moments where it
   was dominant (3 is neutral), blended 70% defaults / 30% adjusted and
   clipped to [0.5×, 1.5×] of the default — pulled toward the defaults,
   blended in gradually.
6. **Check.** CI gate: no overlaps, every clip within min/max, every clip
   has a title, no clip runs past the audio, the source file exists.

## Usage

```bash
# Find moments in a recording (WAV + optional SRT)
python3 -m agent_clip_finder analyze talk.wav --srt talk.srt --out moments.json

# Build a 9:16 clip plan: 3 clips, 30-80 s each
python3 -m agent_clip_finder plan talk.wav --srt talk.srt --count 3 --out plan.json

# Or plan from moments found earlier
python3 -m agent_clip_finder plan talk.wav --moments moments.json --srt talk.srt --out plan.json

# Rate a clip; the weights learn from you
python3 -m agent_clip_finder rate --feedback feedback.jsonl --moment moment-1 --rating 5 \
  --signals '{"loud": 5.0, "voice": 5.0, "words": 1.0}'
python3 -m agent_clip_finder weights --feedback feedback.jsonl

# CI gate for a plan
python3 -m agent_clip_finder check plan.json
# PASS

# Demo on a synthetic recording (quiet talk, two shouts)
python3 -m agent_clip_finder demo --out /tmp/clip-demo
# moments found: 2
#   moment-1: 8.0s-11.0s score=9.3 title='Wow, oh my god, look at this!'
#   moment-2: 18.0s-20.5s score=9.3 title='No way, that was insane!'
# demo plan PASSED the gate
```

The `ffmpeg` command in each clip assumes the source is a video file with
the same timeline as the analysed audio; extract the audio first
(`ffmpeg -i video.mp4 -vn -ac 1 -ar 16000 audio.wav`), run the finder,
then cut the video with the printed commands.

## Tests

```bash
python3 -m unittest discover -s tests
# Ran 42 tests — OK
```

Tests caught 2 real bugs before shipping: the Goertzel band probe hit
exact spectral nulls (a 3 kHz tone leaks exactly zero into 2.5/3.5 kHz
probes over a 100 ms window — fixed with a Hann window plus a 3.0 kHz
probe), and sentence snapping used inclusive boundaries, so a peak at
exactly 8.0 s snapped to the cue that *ended* at 8.0 instead of the one
starting there (fixed with strict comparisons; the later cue wins).

## Honest limits

- Input is a WAV file: you extract the audio yourself (see above). No
  YouTube/Twitch download, no Whisper — if there is no SRT, the `words`
  signal is 0 and the finder works on audio alone.
- 100 ms windows at 16 kHz: a 3-hour recording is ~108k windows; the pure-
  Python Goertzel takes about a minute. Fine for a daily clip run, not
  for live use.
- The keyword list is small and explicit (EN + FA). It marks quotable
  lines; it does not understand what was said. The `words` weight can be
  turned down with a weights file if it misfires on your material.

---

# agent-clip-finder (فارسی)

داغ‌ترین و قابل‌نقل‌ترین لحظه‌های یک ضبط طولانی را پیدا می‌کند — بدون
اینکه کل ویدیو را تماشا کنی. یک CLI کوچک فقط با کتابخانهٔ استاندارد
پایتون: یک فایل WAV و (اختیاری) زیرنویس SRT بده؛ هر پنجرهٔ ۱۰۰
میلی‌ثانیه‌ای را از نظر جهش ناگهانی بلندی صدا، صدای بلندشده (انرژی باند
۲ تا ۴ کیلوهرتز) و کلمه‌های هیجان («wow»، «oh my god» — یا «وای»، «عجب»،
«ایول») امتیاز می‌دهد، قله‌ها را انتخاب می‌کند، ابتدا و انتها را به مرز
جمله می‌چسباند و یک پلن کلیپ ۹:۱۶ (JSON + دستور ffmpeg) تحویل می‌دهد.
با امتیاز ۱ تا ۵ تو هم یاد می‌گیرد: بعد از ۸ امتیاز، وزن سیگنال‌ها به
سمت سلیقهٔ تو تنظیم می‌شود. بدون شبکه، بدون کلید، بدون وابستگی.

**الگو** (کد اورجینال؛ فقط الگو، از رادار امروز):
پروژهٔ iamajmeena/neonclipping ویدیوهای طولانی یوتیوب/توییچ را اول با
صدا به کلیپ ۹:۱۶ زیرنویس‌دار تبدیل می‌کند: فقط صدا را دانلود می‌کند، از
زیرنویس رایگان یوتیوب استفاده می‌کند، جهش بلندی و صدای بلندشده را نسبت
به خط مبنای محلی می‌سنجد، با یک مدل محلی به لحظه امتیاز می‌دهد و تایتل
و هوک می‌نویسد، لبه‌ها را به مرز جمله می‌چسباند و تازه بعد بخش‌های
انتخاب‌شدهٔ ویدیو را دانلود می‌کند. این ابزار همان ایده را به شکل یک CLI
محلی پیاده می‌کند: ‏`analyze`‏ صدا را امتیاز می‌دهد، ‏`plan`‏ پلن کلیپ
می‌سازد، ‏`rate`‏ به وزن‌ها یاد می‌دهد، ‏`weights`‏ آن‌ها را نشان می‌دهد،
‏`check`‏ گیت CI است و ‏`demo`‏ کل مسیر را روی یک ضبط ساختگی اجرا می‌کند.
به‌جای داور LLM از سیگنال کلمه‌های کلیدی زیرنویس (انگلیسی + فارسی)
استفاده شده — همان شکل امتیازدهی، بدون مدل.

## چطور کار می‌کند

۱. **سنجش.** ‏`analyze`‏ فایل WAV را می‌خواند (هر WAV از نوع PCM،
به مونو تبدیل می‌شود) و در پنجره‌های ۱۰۰ میلی‌ثانیه‌ای بلندی (RMS)،
نرخ عبور از صفر و انرژی باند ۲ تا ۴ کیلوهرتز (Goertzel در ۲٫۵/۳/۳٫۵
کیلوهرتز با پنجرهٔ Hann) را می‌سنجد. خط مبنای بلندی محلی است: هر پنجره
با میانهٔ RMS بلوک ۱۲۰ ثانیه‌ای قبلی مقایسه می‌شود.
۲. **امتیاز.** هر پنجره سه امتیاز می‌گیرد: ‏`loud`‏ (RMS نسبت به خط
مبنا، سقف ۵ برابر)، ‏`voice`‏ (انرژی باند نسبت به میانهٔ کل فایل، سقف ۵
برابر) و ‏`words`‏ (کلمهٔ هیجان در کیوی زیرنویس زیر پنجره). مجموع
وزن‌دار با وزن‌های پیش‌فرض ‏`loud 1.0 / voice 0.7 / words 0.8`‏.
۳. **انتخاب.** قله‌ها بهترین پنجره‌ها با حداقل ۸ ثانیه فاصله‌اند که به‌
وضوح از پنجره‌های معمولی بالاتر باشند (نیمه‌راه میانه تا قله). صدای
یکنواخت هیچ لحظه‌ای تولید نمی‌کند. بازهٔ هر لحظه از قله گسترش می‌یابد تا
جایی که پنجره‌های همسایه حداقل نصف امتیاز قله را داشته باشند.
۴. **پلن.** ‏`plan`‏ ابتدا و انتها را به مرز جمله در SRT می‌چسباند،
حداقل/حداکثر طول کلیپ (پیش‌فرض ۳۰ تا ۸۰ ثانیه) را اعمال می‌کند،
کلیپ‌های کم‌امتیازترِ هم‌پوشان را حذف می‌کند و برای هر کلیپ تایتل و هوک
از زیرنویس زیر قله + یک دستور آمادهٔ ‏`ffmpeg`‏ (۱۰۸۰×۱۹۲۰، libx264،
CRF 18) می‌نویسد.
۵. **یادگیری.** ‏`rate --moment moment-1 --rating 5`‏ امتیاز را در
‏`feedback.jsonl`‏ ذخیره می‌کند. بعد از ۸ امتیاز، ‏`weights`‏ وزن‌ها را
تنظیم می‌کند: وزن هر سیگنال به سمت میانگین امتیاز لحظه‌هایی حرکت می‌کند
که آن سیگنال در آن‌ها غالب بوده (۳ خنثی است)، با ترکیب ۷۰٪ پیش‌فرض و
۳۰٪ تنظیم‌شده و محدود به ‏[۰٫۵×، ۱٫۵×]‏ پیش‌فرض.
۶. **گیت.** گیت CI: بدون هم‌پوشانی، هر کلیپ در بازهٔ حداقل/حداکثر، هر
کلیپ تایتل دارد، هیچ کلیپی از انتهای صدا رد نمی‌شود، فایل منبع موجود است.

## استفاده

```bash
# پیدا کردن لحظه‌ها (WAV + زیرنویس اختیاری)
python3 -m agent_clip_finder analyze talk.wav --srt talk.srt --out moments.json

# ساخت پلن کلیپ ۹:۱۶: ۳ کلیپ، هرکدام ۳۰ تا ۸۰ ثانیه
python3 -m agent_clip_finder plan talk.wav --srt talk.srt --count 3 --out plan.json

# امتیاز دادن به یک کلیپ؛ وزن‌ها از تو یاد می‌گیرند
python3 -m agent_clip_finder rate --feedback feedback.jsonl --moment moment-1 --rating 5 \
  --signals '{"loud": 5.0, "voice": 5.0, "words": 1.0}'
python3 -m agent_clip_finder weights --feedback feedback.jsonl

# گیت CI برای پلن
python3 -m agent_clip_finder check plan.json
# PASS

# دمو روی یک ضبط ساختگی (گفت‌وگوی آرام، دو فریاد)
python3 -m agent_clip_finder demo --out /tmp/clip-demo
# moments found: 2
#   moment-1: 8.0s-11.0s score=9.3 title='Wow, oh my god, look at this!'
#   moment-2: 18.0s-20.5s score=9.3 title='No way, that was insane!'
# demo plan PASSED the gate
```

دستور ‏`ffmpeg`‏ هر کلیپ فرض می‌کند منبع یک فایل ویدیویی با همان خط
زمانی صدای تحلیل‌شده است؛ اول صدا را جدا کن
(`ffmpeg -i video.mp4 -vn -ac 1 -ar 16000 audio.wav`)، فایندر را اجرا
کن، بعد ویدیو را با دستورهای چاپ‌شده ببُر.

## تست‌ها

```bash
python3 -m unittest discover -s tests
# Ran 42 tests — OK
```

تست‌ها پیش از انتشار ۲ باگ واقعی گرفتند: پروب باند Goertzel به نال‌های
طیفی دقیق می‌خورد (یک تن ۳ کیلوهرتزی در پنجرهٔ ۱۰۰ میلی‌ثانیه‌ای دقیقاً
صفر به پروب‌های ۲٫۵/۳٫۵ کیلوهرتز نشت می‌کند — با پنجرهٔ Hann و یک پروب
۳٫۰ کیلوهرتزی حل شد)، و چسباندن به مرز جمله از مقایسه‌های غیراکید
استفاده می‌کرد، پس قله‌ای دقیقاً روی ۸٫۰ ثانیه به کیویی می‌چسبید که در
۸٫۰ *تمام* می‌شد نه کیویی که شروع می‌شد (با مقایسه‌های اکید حل شد؛
کیوی بعدی برنده است).

## محدودیت‌های صادقانه

- ورودی فایل WAV است: صدا را خودت جدا می‌کنی (بالا). دانلود یوتیوب/
  توییچ و Whisper ندارد — اگر SRT نباشد سیگنال ‏`words`‏ صفر است و
  فایندر فقط با صدا کار می‌کند.
- پنجره‌های ۱۰۰ میلی‌ثانیه‌ای در ۱۶ کیلوهرتز: یک ضبط ۳ ساعته حدود ۱۰۸
  هزار پنجره است؛ Goertzel با پایتون خالص حدود یک دقیقه طول می‌کشد.
  برای اجرای روزانهٔ کلیپ خوب است، برای استفادهٔ زنده نه.
- فهرست کلمه‌های کلیدی کوچک و صریح است (انگلیسی + فارسی). خط‌های
  قابل‌نقل را علامت می‌زند؛ معنی حرف‌ها را نمی‌فهمد. اگر روی محتوای تو
  اشتباه زد، با فایل وزن‌ها وزن ‏`words`‏ را کم کن.
