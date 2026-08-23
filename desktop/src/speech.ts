export type RecorderOptions = {
  silenceMs?: number;
  maxDurationMs?: number;
  onSilence?: () => void;
  onLevel?: (level: number, speaking: boolean) => void;
};

export type LocalRecorder = {
  stop: () => Promise<Blob>;
  snapshot: () => Promise<Blob>;
  cancel: () => Promise<void>;
};

function downsample(buffer: Float32Array, inputRate: number, outputRate = 16000): Float32Array {
  if (outputRate === inputRate) return buffer;
  const ratio = inputRate / outputRate;
  const length = Math.max(1, Math.round(buffer.length / ratio));
  const result = new Float32Array(length);
  let offset = 0;
  for (let i = 0; i < length; i += 1) {
    const next = Math.min(buffer.length, Math.round((i + 1) * ratio));
    let sum = 0;
    let count = 0;
    for (; offset < next; offset += 1) {
      sum += buffer[offset];
      count += 1;
    }
    result[i] = count ? sum / count : 0;
  }
  return result;
}

function encodeWav(samples: Float32Array, sampleRate = 16000): Blob {
  const bytes = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(bytes);
  const writeString = (offset: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) view.setUint8(offset + i, value.charCodeAt(i));
  };
  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    offset += 2;
  }
  return new Blob([bytes], { type: "audio/wav" });
}

function mergeChunks(chunks: Float32Array[]): Float32Array {
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Float32Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function rms(samples: Float32Array): number {
  if (!samples.length) return 0;
  let sum = 0;
  for (const sample of samples) sum += sample * sample;
  return Math.sqrt(sum / samples.length);
}

export async function startLocalPcmRecorder(options: RecorderOptions = {}): Promise<LocalRecorder> {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone capture is not available");
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const silentGain = context.createGain();
  silentGain.gain.value = 0;
  const chunks: Float32Array[] = [];

  const silenceMs = options.silenceMs ?? 1250;
  const maxDurationMs = options.maxDurationMs ?? 20000;
  const startedAt = performance.now();
  let lastSpeechAt = startedAt;
  let speechStarted = false;
  let silenceSignalled = false;
  let noiseFloor = 0.004;
  let closed = false;

  processor.onaudioprocess = (event) => {
    const chunk = new Float32Array(event.inputBuffer.getChannelData(0));
    chunks.push(chunk);

    const level = rms(chunk);
    const now = performance.now();
    if (!speechStarted) noiseFloor = noiseFloor * 0.94 + level * 0.06;
    const threshold = Math.max(0.009, noiseFloor * 2.8);
    const speaking = level >= threshold;
    options.onLevel?.(level, speaking);

    if (speaking) {
      speechStarted = true;
      lastSpeechAt = now;
      silenceSignalled = false;
    }

    const silentLongEnough = speechStarted && now - lastSpeechAt >= silenceMs;
    const timedOut = now - startedAt >= maxDurationMs;
    if (!silenceSignalled && (silentLongEnough || timedOut)) {
      silenceSignalled = true;
      queueMicrotask(() => options.onSilence?.());
    }
  };
  source.connect(processor);
  processor.connect(silentGain);
  silentGain.connect(context.destination);

  async function cleanup() {
    if (closed) return;
    closed = true;
    processor.disconnect();
    source.disconnect();
    silentGain.disconnect();
    stream.getTracks().forEach((track) => track.stop());
    await context.close();
  }

  async function renderSnapshot(requireMinimum: boolean): Promise<Blob> {
    const merged = mergeChunks(chunks);
    if (requireMinimum && merged.length < context.sampleRate * 0.25) throw new Error("Δεν καταγράφηκε αρκετή ομιλία");
    return encodeWav(downsample(merged, context.sampleRate));
  }

  return {
    snapshot: async () => renderSnapshot(false),
    stop: async () => {
      const snapshot = await renderSnapshot(true);
      await cleanup();
      return snapshot;
    },
    cancel: cleanup,
  };
}
