"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

export default function ExplanatoryLandingPage() {
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="landing-explainer">
      {/* Navigation */}
      <nav className={`fixed-nav ${scrollY > 50 ? "scrolled" : ""}`}>
        <div className="nav-container">
          <div className="nav-logo">
            <div className="logo-icon">Q</div>
            <span className="brand-name">QUANTUS AI</span>
          </div>
          <div className="nav-links">
            <a href="#features">Features</a>
            <Link href="/dashboard" style={{ color: "#22d3a5", fontWeight: 600 }}>Dashboard</Link>
            <Link href="/login" className="btn btn-sm" style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.2)" }}>Sign In</Link>
            <Link href="/login?mode=register" className="btn btn-sm btn-primary">Create Account</Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="hero-section">
        <div className="hero-content">
          <div className="card-badge badge-blue badge-glow mb-6">Built for Institutional-Grade Retail Traders</div>
          <h1 className="hero-headline">
            The Autonomous Trading <br />
            <span className="text-gradient">Intelligence Engine</span>
          </h1>
          <p className="hero-subheadline">
            Quantus AI continuously monitors the Indian stock market. It researches news, analyzes derivatives, rotates sectors, and automatically executes trades across your favorite brokers—all governed by a strict risk management framework.
          </p>
          <div className="hero-actions">
            <Link href="/login?mode=register" className="btn btn-lg btn-primary">Start Trading Automatically</Link>
            <Link href="/dashboard" className="btn btn-lg" style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)" }}>
              <span style={{ marginRight: "8px" }}>▶</span> Watch Live Demo
            </Link>
          </div>
          
          <div className="hero-stats mt-12 grid-3" style={{ maxWidth: "800px", margin: "3rem auto 0", borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: "2rem" }}>
            <div className="stat-block">
              <div className="stat-val">7</div>
              <div className="stat-label">AI Agents</div>
            </div>
            <div className="stat-block">
              <div className="stat-val">0ms</div>
              <div className="stat-label">Execution Latency</div>
            </div>
            <div className="stat-block">
              <div className="stat-val">8+</div>
              <div className="stat-label">Brokers Supported</div>
            </div>
          </div>
        </div>
      </header>

      {/* Features Explainer */}
      <section id="features" className="features-section">
        <div className="section-title-wrap">
          <h2 className="section-title">See Quantus AI In Action</h2>
          <p className="section-subtitle">A brief overview of how our platform transforms your trading experience.</p>
        </div>

        {/* Feature 1: The Dashboard */}
        <div className="feature-row">
          <div className="feature-text">
            <div className="feature-tag badge-purple">Real-Time Intelligence</div>
            <h3>Institutional Grade Dashboard</h3>
            <p>
              Stop switching between 5 different websites. Quantus AI aggregates <strong>News Sentiment, Options Chains, Institutional Flows (FII/DII), and Technical Chart Patterns</strong> into a single, high-performance command center.
            </p>
            <ul className="feature-list">
              <li>✓ Live Market Depth & Options Screeners</li>
              <li>✓ Auto-detection of Head & Shoulders, Wedges, and Double Tops</li>
              <li>✓ AI Earnings Predictor based on historical beat/miss data</li>
            </ul>
          </div>
          <div className="feature-media">
            <div className="media-frame">
              {/* WebP recorded by browser subagent acts as an auto-playing 10s video */}
              <img src="/videos/dashboard.webp" alt="Dashboard Demo" className="demo-video" />
            </div>
          </div>
        </div>

        {/* Feature 2: Sector Heatmap */}
        <div className="feature-row reverse">
          <div className="feature-text">
            <div className="feature-tag badge-green">Sector Rotation</div>
            <h3>Capital Flow Heatmap</h3>
            <p>
              Our proprietary sector rotation model detects where institutional money is moving <em>before</em> breakouts happen. The live heatmap visualizes strength and momentum across all NIFTY sectoral indices instantly.
            </p>
            <ul className="feature-list">
              <li>✓ Visualizes Capital Inflow/Outflow across 14 Sectors</li>
              <li>✓ Auto-alerts on momentum shifts via Telegram/WhatsApp</li>
              <li>✓ Correlates sectoral strength with NIFTY 50 direction</li>
            </ul>
          </div>
          <div className="feature-media">
             <div className="media-frame">
              <img src="/videos/heatmap.webp" alt="Heatmap Demo" className="demo-video" />
            </div>
          </div>
        </div>

        {/* Feature 3: Broker Integration */}
        <div className="feature-row">
          <div className="feature-text">
            <div className="feature-tag badge-blue">Seamless Execution</div>
            <h3>Universal Broker Connection</h3>
            <p>
              Connect your existing demat account without messing with complex API keys. Our universal integration abstracts the heavy technical setup. We manage the API secrets securely on our backend—you just log in natively.
            </p>
            <ul className="feature-list">
              <li>✓ Supports Angel One, Zerodha, Upstox, Fyers, and more</li>
              <li>✓ Enter your Client ID and TOTP, and we handle the rest</li>
              <li>✓ Live Stop-Loss (SL), Take-Profit (TP), and Trailing SL tracking</li>
            </ul>
            <Link href="/login" className="btn btn-primary mt-4">Connect Your Broker Now →</Link>
          </div>
          <div className="feature-media">
            <div className="media-frame">
              <img src="/videos/brokers.webp" alt="Broker Selection Demo" className="demo-video" />
            </div>
          </div>
        </div>

      </section>

      {/* Footer CTA */}
      <section className="footer-cta">
        <h2>Ready to Automate Your Edge?</h2>
        <p>Join elite retail traders leveraging institutional-grade AI today.</p>
        <div className="hero-actions" style={{ justifyContent: "center" }}>
          <Link href="/login?mode=register" className="btn btn-lg btn-primary">Create Free Account</Link>
        </div>
      </section>

      {/* Massive SaaS Footer */}
      <footer className="saas-footer">
        <div className="footer-grid">
          <div className="footer-brand">
            <div className="nav-logo" style={{ marginBottom: "1rem" }}>
              <div className="logo-icon">Q</div>
              <span className="brand-name">QUANTUS AI</span>
            </div>
            <p className="brand-desc">
              Autonomous algorithmic trading and deep market research powered by 7 specialized AI agents. Built for results.
            </p>
            <div className="social-links">
              <a href="#" aria-label="Twitter">𝕏</a>
              <a href="#" aria-label="GitHub">🐙</a>
              <a href="#" aria-label="LinkedIn">💼</a>
              <a href="#" aria-label="Email">✉️</a>
            </div>
          </div>
          
          <div className="footer-column">
            <h4>Product</h4>
            <Link href="/dashboard">Dashboard</Link>
            <a href="#features">Features</a>
            <a href="#">Pricing</a>
            <a href="#">Auto-Trader</a>
            <a href="#">Backtest Studio</a>
          </div>

          <div className="footer-column">
            <h4>Resources</h4>
            <a href="#">Documentation</a>
            <a href="#">API Reference</a>
            <a href="#">Changelog</a>
            <a href="#">System Status</a>
          </div>

          <div className="footer-column">
            <h4>Company</h4>
            <a href="#">About Us</a>
            <a href="#">Manifesto</a>
            <a href="#">Careers</a>
            <a href="#">Contact</a>
          </div>

          <div className="footer-column">
            <h4>Legal</h4>
            <a href="#">Privacy Policy</a>
            <a href="#">Terms of Service</a>
            <a href="#">Risk Disclosure</a>
            <a href="#">SEBI Compliance</a>
          </div>
        </div>
        
        <div className="footer-bottom">
          <span>© 2026 Quantus AI. All rights reserved.</span>
          <span className="footer-meta">Capital preservation is priority #1.</span>
        </div>
      </footer>

      <style jsx>{`
        .landing-explainer {
          background-color: #030508;
          color: white;
          font-family: 'Space Grotesk', sans-serif;
          min-height: 100vh;
        }

        .fixed-nav {
          position: fixed;
          top: 0; left: 0; right: 0;
          height: 70px;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          transition: background 0.3s ease, border-bottom 0.3s ease;
        }

        .fixed-nav.scrolled {
          background: rgba(3, 5, 8, 0.85);
          backdrop-filter: blur(12px);
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .nav-container {
          width: 100%;
          max-width: 1200px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0 2rem;
        }

        .nav-logo {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          font-weight: 700;
          letter-spacing: 1px;
        }

        .nav-links {
          display: flex;
          align-items: center;
          gap: 1.5rem;
        }

        .nav-links a:not(.btn) {
          color: rgba(255,255,255,0.7);
          text-decoration: none;
          font-size: 0.9rem;
          transition: color 0.2s;
        }

        .nav-links a:not(.btn):hover {
          color: white;
        }

        .hero-section {
          padding: 160px 2rem 100px;
          display: flex;
          justify-content: center;
          background: radial-gradient(circle at center top, rgba(34,211,165,0.08) 0%, transparent 60%);
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .hero-content {
          max-width: 900px;
          text-align: center;
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .hero-headline {
          font-size: 4.5rem;
          line-height: 1.1;
          font-weight: 700;
          margin-bottom: 1.5rem;
          letter-spacing: -1.5px;
        }

        .text-gradient {
          background: linear-gradient(90deg, #fff, #22d3a5);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .hero-subheadline {
          font-size: 1.25rem;
          color: rgba(255,255,255,0.6);
          max-width: 700px;
          line-height: 1.6;
          margin-bottom: 2.5rem;
        }

        .hero-actions {
          display: flex;
          gap: 1rem;
        }

        .stat-block .stat-val {
          font-size: 2.5rem;
          font-weight: 700;
          color: white;
        }

        .stat-block .stat-label {
          color: #888;
          font-size: 0.9rem;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-top: 0.5rem;
        }

        .features-section {
          padding: 100px 2rem;
          max-width: 1200px;
          margin: 0 auto;
        }

        .section-title-wrap {
          text-align: center;
          margin-bottom: 80px;
        }

        .section-title {
          font-size: 3rem;
          font-weight: 700;
          margin-bottom: 1rem;
        }

        .section-subtitle {
          color: #888;
          font-size: 1.2rem;
        }

        .feature-row {
          display: flex;
          align-items: center;
          gap: 4rem;
          margin-bottom: 120px;
        }

        .feature-row.reverse {
          flex-direction: row-reverse;
        }

        @media (max-width: 900px) {
          .feature-row, .feature-row.reverse {
            flex-direction: column;
            gap: 2rem;
          }
        }

        .feature-text {
          flex: 1;
        }

        .feature-tag {
          display: inline-block;
          margin-bottom: 1rem;
        }

        .feature-text h3 {
          font-size: 2.2rem;
          margin-bottom: 1.5rem;
          font-weight: 600;
        }

        .feature-text p {
          color: #999;
          font-size: 1.1rem;
          line-height: 1.7;
          margin-bottom: 1.5rem;
        }

        .feature-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .feature-list li {
          margin-bottom: 0.8rem;
          color: #ddd;
          display: flex;
          align-items: center;
          font-size: 1rem;
        }

        .feature-media {
          flex: 1;
          display: flex;
          justify-content: center;
        }

        .media-frame {
          background: rgba(255,255,255,0.02);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 12px;
          padding: 0.5rem;
          box-shadow: 0 20px 50px rgba(0,0,0,0.5);
          width: 100%;
        }

        .demo-video {
          width: 100%;
          border-radius: 8px;
          display: block;
          /* Small scale animation on hover */
          transition: transform 0.3s ease;
        }

        .demo-video:hover {
          transform: scale(1.02);
        }

        .footer-cta {
          padding: 100px 2rem;
          text-align: center;
          border-top: 1px solid rgba(255,255,255,0.05);
          background: linear-gradient(to top, rgba(34,211,165,0.05), transparent);
        }

        .footer-cta h2 {
          font-size: 2.5rem;
          margin-bottom: 1rem;
        }

        .footer-cta p {
          color: #888;
          font-size: 1.2rem;
          margin-bottom: 2rem;
        }

        .saas-footer {
          border-top: 1px solid rgba(255,255,255,0.05);
          padding: 80px 2rem 40px;
          background: #020305;
        }

        .footer-grid {
          max-width: 1200px;
          margin: 0 auto;
          display: grid;
          grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
          gap: 3rem;
          padding-bottom: 60px;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        @media (max-width: 900px) {
          .footer-grid {
            grid-template-columns: 1fr 1fr;
          }
          .footer-brand {
            grid-column: 1 / -1;
          }
        }

        .brand-desc {
          color: rgba(255,255,255,0.5);
          font-size: 0.95rem;
          line-height: 1.6;
          max-width: 300px;
          margin-bottom: 1.5rem;
        }

        .social-links {
          display: flex;
          gap: 1rem;
        }

        .social-links a {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background: rgba(255,255,255,0.03);
          border: 1px solid rgba(255,255,255,0.1);
          color: rgba(255,255,255,0.7);
          text-decoration: none;
          transition: all 0.2s;
        }

        .social-links a:hover {
          background: rgba(255,255,255,0.1);
          color: white;
          border-color: rgba(255,255,255,0.3);
        }

        .footer-column h4 {
          color: white;
          font-weight: 600;
          margin-bottom: 1.5rem;
          font-size: 1.05rem;
        }

        .footer-column a {
          display: block;
          color: rgba(255,255,255,0.5);
          text-decoration: none;
          margin-bottom: 0.8rem;
          font-size: 0.95rem;
          transition: color 0.2s;
        }

        .footer-column a:hover {
          color: #22d3a5;
        }

        .footer-bottom {
          max-width: 1200px;
          margin: 40px auto 0;
          display: flex;
          justify-content: space-between;
          align-items: center;
          color: rgba(255,255,255,0.4);
          font-size: 0.85rem;
        }

        @media (max-width: 600px) {
          .footer-bottom {
            flex-direction: column;
            gap: 1rem;
            text-align: center;
          }
        }

        .footer-meta {
          color: rgba(255,255,255,0.3);
        }
      `}</style>
    </div>
  );
}
