/**
 * CyberAudio - Procedural Web Audio API Sound Synthesizer for mefresh
 * Generates ultra-futuristic sci-fi UI soundscapes with zero external assets.
 */
class CyberAudio {
    constructor() {
        this.ctx = null;
        this.muted = false;
        this.volume = 0.35;
        this.initialized = false;
    }

    init() {
        if (!this.initialized) {
            try {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                this.ctx = new AudioContext();
                this.initialized = true;
            } catch (e) {
                console.warn("Web Audio API not supported", e);
            }
        }
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    setMuted(muted) {
        this.muted = muted;
    }

    setVolume(vol) {
        this.volume = Math.max(0, Math.min(1, vol));
    }

    playTone(freq, type, duration, startGain, endGain, freqEnd = null) {
        if (this.muted) return;
        this.init();
        if (!this.ctx) return;

        try {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();

            osc.type = type;
            osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
            if (freqEnd !== null) {
                osc.frequency.exponentialRampToValueAtTime(Math.max(freqEnd, 20), this.ctx.currentTime + duration);
            }

            gain.gain.setValueAtTime(startGain * this.volume, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(Math.max(endGain, 0.0001) * this.volume, this.ctx.currentTime + duration);

            osc.connect(gain);
            gain.connect(this.ctx.destination);

            osc.start();
            osc.stop(this.ctx.currentTime + duration);
        } catch (e) {
            // Audio error suppression
        }
    }

    // Sound FX Library

    click() {
        this.playTone(1800, 'triangle', 0.04, 0.4, 0.01, 800);
    }

    hover() {
        this.playTone(3200, 'sine', 0.02, 0.15, 0.001);
    }

    toggle() {
        this.playTone(1200, 'sine', 0.05, 0.3, 0.01, 1600);
    }

    packageAdd() {
        this.playTone(600, 'sine', 0.12, 0.4, 0.01, 1800);
        setTimeout(() => {
            this.playTone(1800, 'triangle', 0.08, 0.3, 0.01, 2400);
        }, 60);
    }

    restorePoint() {
        // Deep futuristic cyber shield resonance
        this.playTone(150, 'sawtooth', 0.5, 0.5, 0.01, 400);
        setTimeout(() => {
            this.playTone(600, 'sine', 0.4, 0.4, 0.01, 1200);
        }, 150);
    }

    deployStart() {
        // Sci-fi warp ignition sound
        this.playTone(200, 'sawtooth', 0.6, 0.5, 0.01, 1200);
        setTimeout(() => {
            this.playTone(1200, 'sine', 0.4, 0.4, 0.01, 2400);
        }, 200);
    }

    itemSuccess() {
        // Futuristic double chime
        this.playTone(1046.5, 'sine', 0.1, 0.35, 0.01); // C6
        setTimeout(() => {
            this.playTone(1318.5, 'sine', 0.18, 0.4, 0.01); // E6
        }, 80);
    }

    itemFailed() {
        // Low error buzz
        this.playTone(220, 'sawtooth', 0.25, 0.6, 0.01, 110);
    }

    completeFanfare() {
        // 4-note victory cyber chord
        const notes = [523.25, 659.25, 783.99, 1046.5];
        notes.forEach((freq, idx) => {
            setTimeout(() => {
                this.playTone(freq, 'triangle', 0.25, 0.4, 0.01);
            }, idx * 90);
        });
    }

    warning() {
        this.playTone(880, 'square', 0.15, 0.3, 0.01, 440);
    }
}

const cyberAudio = new CyberAudio();
