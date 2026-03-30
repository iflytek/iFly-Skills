---
name: ifly-voiceclone-tts
description: "iFlytek Voice Clone tts(声音复刻) — train a custom voice model from audio samples and synthesize speech with the cloned voice. Supports the full workflow: get training text → create task → upload audio → submit training → poll results → synthesize with cloned voice. Pure Python stdlib, no pip dependencies."
---

# ifly-voiceclone-tts

Clone a voice from audio samples and synthesize speech with it, using iFlytek's Voice Clone (声音复刻) API. Two-phase workflow: **train** a voice model, then **synthesize** speech with it.

## Setup

1. Create an app at [讯飞控制台](https://console.xfyun.cn) with **一句话声音复刻** service enabled
2. Set environment variables:
   ```bash
   export IFLY_APP_ID="your_app_id"
   export IFLY_API_KEY="your_api_key"
   export IFLY_API_SECRET="your_api_secret"
   ```

## Workflow

### Phase 1: Train a Voice Model

#### Step 1 — Get training text

```bash
python3 scripts/voiceclone.py train get-text
```

This returns a list of text segments with `segId`. You need to record yourself reading one of these texts.

#### Step 2 — Create a training task

```bash
python3 scripts/voiceclone.py train create --name "MyVoice" --sex female --engine omni_v1
```

Returns `task_id`. Supported engines:
- `omni_v1` — Multi-style universal voice (recommended)

Gender: `male`/`female` (or `1`/`2`).

#### Step 3 — Upload audio

```bash
# Local file:
python3 scripts/voiceclone.py train upload --task-id 12345 --audio recording.wav --text-id 5001 --seg-id 1

# URL:
python3 scripts/voiceclone.py train upload --task-id 12345 --audio-url "https://example.com/voice.wav" --text-id 5001 --seg-id 1
```

Audio requirements:
- Format: WAV/MP3/M4A/PCM
- Duration: match the training text (typically 3-60 seconds)
- Quality: clear recording, minimal background noise

#### Step 4 — Submit for training

```bash
python3 scripts/voiceclone.py train submit --task-id 12345
```

#### Step 5 — Check status (poll until done)

```bash
python3 scripts/voiceclone.py train status --task-id 12345
```

When complete, returns the `res_id` (voice resource ID) needed for synthesis.

#### Quick one-shot training

```bash
python3 scripts/voiceclone.py train quick \
    --audio recording.wav \
    --name "MyVoice" \
    --sex female \
    --wait
```

This combines create → upload → submit → poll in one command. `--wait` polls every 30s until training completes and prints the `res_id`.

### Phase 2: Synthesize Speech

```bash
# Basic synthesis
python3 scripts/voiceclone.py synth "你好，这是我的声音克隆。" --res-id YOUR_RES_ID

# With output file
python3 scripts/voiceclone.py synth "Hello world" --res-id YOUR_RES_ID --output hello.mp3

# From file
python3 scripts/voiceclone.py synth --file article.txt --res-id YOUR_RES_ID -o article.mp3

# From stdin
echo "测试语音合成" | python3 scripts/voiceclone.py synth --res-id YOUR_RES_ID

# Adjust parameters
python3 scripts/voiceclone.py synth "快一点" --res-id YOUR_RES_ID --speed 70 --volume 80
```

## Train Subcommands

| Command | Description |
|---------|-------------|
| `train get-text` | Get training text segments |
| `train create` | Create a training task |
| `train upload` | Upload audio to a task |
| `train submit` | Submit task for training |
| `train status` | Check training status |
| `train quick` | One-shot: create + upload + submit |

## Synthesis Options

| Flag | Default | Description |
|------|---------|-------------|
| `--res-id` | (required) | Voice resource ID from training |
| `--output` / `-o` | `output.mp3` | Output audio file path |
| `--format` | `mp3` | Audio format: mp3, pcm, speex, opus |
| `--sample-rate` | `16000` | Sample rate: 8000, 16000, 24000 |
| `--speed` | `50` | Speed 0–100 (50=normal) |
| `--volume` | `50` | Volume 0–100 (50=normal) |
| `--pitch` | `50` | Pitch 0–100 (50=normal) |

## Notes

- **Training API**: HTTP REST at `http://opentrain.xfyousheng.com/voice_train` (MD5-based token auth)
- **Synthesis API**: WebSocket at `wss://cn-huabei-1.xf-yun.com/v1/private/voice_clone` (HMAC-SHA256 URL auth)
- **vcn**: always `x6_clone` for cloned voice synthesis
- **Engine `omni_v1`**: multi-style universal voice, supports cn/en/jp/ko/ru
- **Training text**: use `get-text` to find available text segments — you must record yourself reading the corresponding text
- **Training time**: typically 2–10 minutes depending on load
- **No pip dependencies**: uses pure Python stdlib (built-in WebSocket client)
- **Env vars**: `IFLY_APP_ID`, `IFLY_API_KEY`, `IFLY_API_SECRET`
- **Output**: prints absolute path of saved audio to stdout
- **API doc**: https://www.xfyun.cn/doc/spark/voiceclone.html

## 常见错误码速查指南 ฅ⁽͑˙˙⁾ฅ

遇到错误先别慌～看看下面的错误码对照表就知道怎么办啦 ✧｡･ﾟ:*･

### 🎤 音色训练接口 - 常见错误码

| 错误码 | 哎呀！发生了什么？ | 怎么解决呢？ |
|--------|-------------------|-------------|
| **10000** | token过期啦～时间到惹 (ˊᵕˋ) | 检查一下token是不是过期了，去刷新一下token吧！ |
| **10001** | 缺少请求头参数哦 (⊙_⊙) | 看看请求头有没有带`X-AppId`和`X-Token`，要加上去哦～ |
| **10015** | 这个训练任务不是你的呀 (›´ω`‹ ) | 这个任务不属于当前应用，检查一下appid对不对呢～ |
| **10016** | appid无效啦～ (°°) | 這個appid沒有被授權，聯繫訊飛大大們給你分配一個吧！ |
| **10017** | 未授权这个训练类型呢 (๑•́ ₃ •̀๑) | 这个训练类型没权限，联系讯飞技术人员帮你开通吧～ |
| **10018** | 没有分配训练路数哦 (｡•́︿•̀｡) | 训练路数授权不够用啦！联系讯飞业务员增加训练路数吧～ |
| **10019** | appid授权已过期惹 (╥_╥) | 授权到期啦！联系业务员看看能不能续期吧～ |
| **10020** | IP地址没授权呢 (⊙﹏⊙) | 你的IP地址不在白名单里，把IP给讯飞让他们加一下吧！ |
| **10021** | 没有分配训练次数哦 (´；ω；`) | 训练次数用完了！联系讯飞爸爸增加次数吧～ |
| **20001** | textId无效或训练文本是空的呀 (°°) | 检查一下textId和textSegId对不对，可以用`train get-text`命令确认一下哦！ |
| **20002** | textSegId无效啦 (⊙_⊙) | 这个分段ID不存在呢，用`train get-text`看看有哪些有效的ID吧！ |
| **60000** | 训练任务不存在哦 (；ω；`) | 看看taskId是不是填错了呀？检查一下再试试吧～ |
| **90001** | 请求非法啦 (°°) | 按照接口协议检查一下请求结构对不对哦～ |
| **90002** | 请求参数不正确 (´；ω；`) | 参数有问题的说...比如textId must not be blank这种，仔细看看错误提示吧！ |
| **99999** | 系统内部异常啦 (╥_╥) | 这个比较复杂...请联系讯飞技术人员帮你排查一下吧！ |

> 💡 **小贴士**：如果是权限、授权相关的问题（10016-10021），基本上都需要联系讯飞官方处理哦～可以提交工单：https://console.xfyun.cn/workorder/commit

---

### 🎵 音频合成接口 - 常见错误码

| 错误码 | 哎呀！发生了什么？ | 怎么解决呢？ |
|--------|-------------------|-------------|
| **10009** | 输入数据非法啦 (⊙_⊙) | 检查一下输入的数据格式对不对哦～ |
| **10010** | 授权数已满惹 (°°) | 没有授权许可或数量用光啦！提交工单联系讯飞吧～ |
| **10019** | session超时啦 (ˊᵕˋ) | 检查一下数据发送完了有没有关闭连接呢～ |
| **10043** | 音频解码失败惹 (｡•́︿•̀｡) | 检查`aue`参数！如果填的是speex，要确保音频真的是speex格式，并且分段压缩和帧大小要一致哦～ |
| **10114** | session超时啦 (´；ω；`) | 会话时间太长了，检查一下发送数据有没有超过60秒哦～ |
| **10139** | 参数错误啦 (⊙_⊙) | 看看参数有没有写错呢～ |
| **10160** | 请求JSON格式非法 (°°) | 检查一下发送的数据是不是合法的JSON格式呀～ |
| **10161** | base64解码失败惹 (╥_╥) | 检查一下数据有没有用base64编码哦～ |
| **10163** | 参数校验失败啦 (´；ω；`) | 具体原因看详细描述吧～仔细对照接口文档看看哪里的问题呢？ |
| **10200** | 读取数据超时 (°°) | 检查一下是不是累计10秒没发送数据又没关闭连接呀？ |
| **10222** | 上传数据超限或SSL问题 (⊙﹏⊙) | 1. 检查一下上传的数据（文本、音频、图片等）有没有超过接口上限～ <br/> 2. SSL证书问题的话，把log导出发到工单吧：https://console.xfyun.cn/workorder/commit |
| **10223** | LB找不到节点 (°°) | 服务器内部问题，提交工单吧～ |
| **10313** | appid和apikey不匹配 (⊙_⊙) | 检查一下appid是不是正确合法的哦～ |
| **10317** | 版本非法啦 (°°) | 版本号不对呢，提交工单联系技术人员处理吧！ |
| **10700** | 引擎异常 (´；ω；`) | 按照报错原因对照开发文档检查输入输出，如果还是搞不定，提供sid和错误信息提交工单吧！ |
| **11200** | 功能未授权 (°°) | 先检查appid对不对，确保appid下添加了相关服务哦！<br/>• 看看总调用量是不是超了或到期了<br/>• 确认功能授权情况<br/>如果都没问题就联系商务人员吧～ |
| **11201** | 每日交互次数超限啦 (╥_╥) | 次数用光啦！可以提交应用审核提额，或者联系商务购买企业级接口获得海量服务量哦～ |
| **11503** | 服务内部响应数据错误 (°°) | 提交工单让讯飞大大们看看怎么回事吧！ |
| **11502** | 服务配置错误 (⊙_⊙) | 这个是讯飞的问题，提交工单吧～ |
| **100001~100010** | 引擎调用错误 (´；ω；`) | 请提供sid和错误信息，提交工单联系技术人员排查吧！ |

> 💡 **超重要！** 错误码100001-100010可能是引擎层面的问题，提交工单时记得提供：
> - **sid**（请求会话ID）
> - **完整的错误信息**
> - **复现步骤**
>
> 这样技术人员才能快速帮你定位问题哦～ ✧٩(ˊᗜˋ*)و

---

### 🆘 遇到问题怎么办？

1. **先看错误码**：上面的表格基本上涵盖了常见错误，看看有没有对应的～ ๑•̀ㅂ•́)و✧
2. **检查参数**：很多错误都是参数写错导致的，对照接口文档仔细核对一下哦！
3. **提交工单**：如果表格里没有，或者搞不定，点击这里提交工单：https://console.xfyun.cn/workorder/commit
4. **购买/升级服务**：需要更多调用量或功能的话：
   - [一句话声音复刻控制台](https://console.xfyun.cn/services/oneSentenceV2)
   - [购买服务包](https://console.xfyun.cn/sale/buy?wareId=9188&packageId=9188001&serviceName=%E4%B8%80%E5%8F%A5%E8%AF%9D%E5%A4%8D%E5%88%BB%EF%BC%88%E5%A4%9A%E9%A3%8E%E6%A0%BC%E7%89%88%EF%BC%89&businessId=oneSentenceV2)

> 🎉 **祝你开发顺利！** 如果有其他问题也可以随时问我哦～ 一起加油！(´▽`ʃ♡ƪ)
