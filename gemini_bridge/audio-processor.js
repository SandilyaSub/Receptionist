// audio-processor.js
class PcmProcessor extends AudioWorkletProcessor {
    constructor(options) {
        super(options);
        // processorOptions can be passed from the main thread if needed
        // e.g., options.processorOptions.targetSampleRate
        // For now, we assume the AudioContext is already at 16kHz
        this.bufferSize = options.processorOptions?.bufferSize || 2048; // Send data when buffer reaches this size
        this._buffer = new Int16Array(this.bufferSize);
        this._bufferIndex = 0;
        this.totalSamplesProcessed = 0;
    }

    process(inputs, outputs, parameters) {
        // We expect a single input, and we'll process the first channel (mono).
        const input = inputs[0];
        if (!input || input.length === 0) {
            return true; // Keep processor alive
        }

        const inputChannel = input[0]; // Assuming mono, or taking the first channel

        if (!inputChannel) {
            return true;
        }

        // Convert Float32 samples (-1.0 to 1.0) to Int16 PCM (-32768 to 32767)
        for (let i = 0; i < inputChannel.length; i++) {
            const floatSample = inputChannel[i];
            // Clamp and convert
            const pcmSample = Math.max(-1, Math.min(1, floatSample)) * 32767;
            this._buffer[this._bufferIndex++] = pcmSample;

            if (this._bufferIndex >= this.bufferSize) {
                // Buffer is full, send it to the main thread
                this.port.postMessage({
                    type: 'audioData',
                    buffer: this._buffer.slice(0, this._bufferIndex) // Send a copy
                });
                this._bufferIndex = 0; // Reset buffer index
            }
        }
        this.totalSamplesProcessed += inputChannel.length;

        // Return true to keep the processor alive
        return true;
    }
}

registerProcessor('pcm-processor', PcmProcessor);
