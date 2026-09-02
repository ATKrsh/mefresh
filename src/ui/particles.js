/**
 * Ultra-Lightweight Futuristic Cyber Background Canvas
 * Fully throttled, zero GPU load when hidden/idle, squared-distance optimized.
 */
class CyberBackground {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d', { alpha: true });
        this.particles = [];
        this.particleCount = 28;
        this.maxDistance = 120;
        this.maxDistSq = this.maxDistance * this.maxDistance;
        this.scanlineY = 0;
        this.scanSpeed = 1.0;
        this.mouse = { x: null, y: null, radius: 120, radiusSq: 14400 };
        this.isPaused = false;

        this.init();
        this.bindEvents();
        this.animate();
    }

    init() {
        this.resize();
        this.particles = [];
        for (let i = 0; i < this.particleCount; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                radius: Math.random() * 1.5 + 1,
                color: Math.random() > 0.4 ? '#00f0ff' : '#b026ff'
            });
        }
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    bindEvents() {
        window.addEventListener('resize', () => this.resize(), { passive: true });
        
        // Pause animation when tab or window is in background
        document.addEventListener('visibilitychange', () => {
            this.isPaused = document.hidden;
            if (!this.isPaused) {
                requestAnimationFrame(() => this.animate());
            }
        });

        window.addEventListener('mousemove', (e) => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        }, { passive: true });

        window.addEventListener('mouseleave', () => {
            this.mouse.x = null;
            this.mouse.y = null;
        }, { passive: true });
    }

    animate() {
        if (this.isPaused || document.hidden) return;

        requestAnimationFrame(() => this.animate());
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // 1. Subtle Cyber Grid Lines (batch path)
        this.ctx.strokeStyle = 'rgba(0, 240, 255, 0.02)';
        this.ctx.lineWidth = 1;
        this.ctx.beginPath();
        const gridSize = 60;
        for (let x = 0; x < this.canvas.width; x += gridSize) {
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, this.canvas.height);
        }
        for (let y = 0; y < this.canvas.height; y += gridSize) {
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(this.canvas.width, y);
        }
        this.ctx.stroke();

        // 2. Update & Draw Particles with Batch Path Connecting
        const len = this.particles.length;
        for (let i = 0; i < len; i++) {
            const p = this.particles[i];

            p.x += p.vx;
            p.y += p.vy;

            if (p.x < 0 || p.x > this.canvas.width) p.vx *= -1;
            if (p.y < 0 || p.y > this.canvas.height) p.vy *= -1;

            // Draw Node
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.radius, 0, 6.283);
            this.ctx.fillStyle = p.color;
            this.ctx.fill();

            // Connect to other nodes with fast squared-distance check
            for (let j = i + 1; j < len; j++) {
                const p2 = this.particles[j];
                const dx = p.x - p2.x;
                const dy = p.y - p2.y;
                const distSq = dx * dx + dy * dy;

                if (distSq < this.maxDistSq) {
                    const alpha = (1 - Math.sqrt(distSq) / this.maxDistance) * 0.18;
                    this.ctx.strokeStyle = `rgba(0, 240, 255, ${alpha})`;
                    this.ctx.lineWidth = 0.7;
                    this.ctx.beginPath();
                    this.ctx.moveTo(p.x, p.y);
                    this.ctx.lineTo(p2.x, p2.y);
                    this.ctx.stroke();
                }
            }

            // Connect to mouse with fast squared-distance check
            if (this.mouse.x !== null) {
                const mdx = p.x - this.mouse.x;
                const mdy = p.y - this.mouse.y;
                const mdistSq = mdx * mdx + mdy * mdy;
                if (mdistSq < this.mouse.radiusSq) {
                    const malpha = (1 - Math.sqrt(mdistSq) / this.mouse.radius) * 0.3;
                    this.ctx.strokeStyle = `rgba(176, 38, 255, ${malpha})`;
                    this.ctx.lineWidth = 0.8;
                    this.ctx.beginPath();
                    this.ctx.moveTo(p.x, p.y);
                    this.ctx.lineTo(this.mouse.x, this.mouse.y);
                    this.ctx.stroke();
                }
            }
        }
    }
}
