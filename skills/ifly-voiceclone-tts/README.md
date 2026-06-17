# iFly Voice Clone TTS

基于讯飞声音复刻能力，先训练自定义音色，再用训练出来的 `res_id` 合成语音。对应脚本为 `scripts/voiceclone.py`，纯 Python 标准库实现。

## 前置条件

```bash
export IFLY_APP_ID="your_app_id"
export IFLY_API_KEY="your_api_key"
export IFLY_API_SECRET="your_api_secret"
```

## 快速开始

```bash
# 一键训练音色并等待完成
python3 scripts/voiceclone.py train quick \
  --audio ./recording.wav \
  --name "MyVoice" \
  --sex female \
  --wait

# 使用训练好的 res_id 合成语音
python3 scripts/voiceclone.py synth "你好，这是我的声音克隆。" --res-id YOUR_RES_ID -o hello.mp3

# 从文件批量合成
python3 scripts/voiceclone.py synth --file ./article.txt --res-id YOUR_RES_ID -o article.mp3
```

## 工作流概览

1. 获取训练文本
2. 创建训练任务
3. 上传音频样本
4. 提交训练
5. 查询训练状态，拿到 `res_id`
6. 使用 `res_id` 做语音合成

## 训练音色

```bash
# 获取可朗读的训练文本
python3 scripts/voiceclone.py train get-text

# 创建训练任务
python3 scripts/voiceclone.py train create --name "MyVoice" --sex female

# 上传本地音频
python3 scripts/voiceclone.py train upload --task-id 12345 --audio ./recording.wav --text-id 5001 --seg-id 1

# 提交训练
python3 scripts/voiceclone.py train submit --task-id 12345

# 查询状态
python3 scripts/voiceclone.py train status --task-id 12345
```

一键训练：

```bash
python3 scripts/voiceclone.py train quick \
  --audio ./recording.wav \
  --name "MyVoice" \
  --sex female \
  --wait
```

## 合成语音

```bash
# 直接输入文本
python3 scripts/voiceclone.py synth "你好，这是我的声音克隆。" --res-id YOUR_RES_ID

# 保存到文件
python3 scripts/voiceclone.py synth "Hello world" --res-id YOUR_RES_ID -o hello.mp3

# 从文件读取文本
python3 scripts/voiceclone.py synth --file ./article.txt --res-id YOUR_RES_ID -o article.mp3

# 调整语速、音量、音调
python3 scripts/voiceclone.py synth "快一点" --res-id YOUR_RES_ID --speed 70 --volume 80 --pitch 55
```

## 训练子命令

| 命令 | 说明 |
|------|------|
| `train get-text` | 获取训练文本片段 |
| `train create` | 创建训练任务 |
| `train upload` | 上传本地音频或公网音频 URL |
| `train submit` | 提交训练 |
| `train status` | 查询训练状态 |
| `train quick` | 串联创建、上传、提交，可选等待完成 |

## 常用参数

### `train create`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--name` | 任务名 | 必填 |
| `--sex` | `male` / `female` / `1` / `2` | 必填 |
| `--engine` | 引擎版本 | `omni_v1` |
| `--language` | `cn` / `en` / `jp` / `ko` / `ru` | `cn` |
| `--resource-name` | 资源名 | 与任务名相同 |

### `synth`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `text` | 要合成的文本 | 可选 |
| `--file`, `-f` | 从文件读取文本 | 不传 |
| `--res-id` | 训练完成后的音色资源 ID | 必填 |
| `--output`, `-o` | 输出文件路径 | `output.mp3` |
| `--format` | `mp3` / `pcm` / `speex` / `opus` | `mp3` |
| `--sample-rate` | `8000` / `16000` / `24000` | `16000` |
| `--speed` | 语速 `0-100` | `50` |
| `--volume` | 音量 `0-100` | `50` |
| `--pitch` | 音调 `0-100` | `50` |

## 限制说明

- 训练音频支持 `wav`、`mp3`、`m4a`、`pcm`。
- 录音内容需要和训练文本片段匹配。
- 推荐使用清晰、无明显噪音的单人录音。
- 默认训练引擎为 `omni_v1`，合成时固定使用 `x6_clone`。
- 完整文档与错误码说明见 [`SKILL.md`](./SKILL.md)。

## 参考链接

- 官方文档：https://www.xfyun.cn/doc/spark/voiceclone.html
- 控制台：https://console.xfyun.cn/services/oneSentenceV2
- 服务购买：https://console.xfyun.cn/sale/buy?wareId=9188&packageId=9188001
