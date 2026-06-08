// Thu âm micro -> Blob WAV 16-bit. Encode WAV ngay trên browser để backend
// (soundfile/omnivoice) đọc được - MediaRecorder mặc định ra webm/opus thì không đọc nổi.

class WavRecorder {
  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.node = this.ctx.createScriptProcessor(4096, 1, 1);
    this.chunks = [];
    this.length = 0;
    this.node.onaudioprocess = (e) => {
      const ch = e.inputBuffer.getChannelData(0);
      this.chunks.push(new Float32Array(ch));
      this.length += ch.length;
    };
    this.source.connect(this.node);
    this.node.connect(this.ctx.destination);
  }

  stop() {
    this.node.disconnect();
    this.source.disconnect();
    this.stream.getTracks().forEach((t) => t.stop());
    const rate = this.ctx.sampleRate;
    this.ctx.close();
    const data = new Float32Array(this.length);
    let offset = 0;
    for (const c of this.chunks) { data.set(c, offset); offset += c.length; }
    return encodeWav(data, rate);
  }
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (off, s) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)); };

  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);           // PCM header size
  view.setUint16(20, 1, true);            // format = PCM
  view.setUint16(22, 1, true);            // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);            // block align
  view.setUint16(34, 16, true);           // bits per sample
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}
