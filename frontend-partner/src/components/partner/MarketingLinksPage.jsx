import React, { useState, useEffect } from 'react';
import { Share2, Copy, Check, Link2, ExternalLink, QrCode, Shield, Sparkles, Award } from 'lucide-react';
import { partnerApi } from '../../api/partnerApi';
import { useToast } from '../../context/ToastContext';

export const MarketingLinksPage = () => {
  const { addToast } = useToast();
  const [links, setLinks] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copiedKey, setCopiedKey] = useState(null);

  // UTM Campaign Generator State
  const [campaignName, setCampaignName] = useState('telegram_channel');
  const [campaignMedium, setCampaignMedium] = useState('social');

  useEffect(() => {
    const loadLinks = async () => {
      try {
        const res = await partnerApi.getMarketingLinks();
        setLinks(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadLinks();
  }, []);

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    addToast('Link copied to clipboard! 📋', 'success');
    setTimeout(() => setCopiedKey(null), 3000);
  };

  const refCode = links?.referralCode || 'REF-PARTNER77';
  const baseRefLink = links?.referralLink || `https://zenalgo.com/register?ref=${refCode}`;
  const customUtmLink = `${baseRefLink}&utm_source=${campaignName}&utm_medium=${campaignMedium}`;
  const dhanPartnerUrl = links?.dhanPartnerOnboardingUrl || `https://invite.dhan.co/?join=${refCode}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Broker Onboarding & Marketing Links</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Generate zero-friction Dhan broker partner consent links and custom referral campaign URLs.
        </p>
      </div>

      {/* Primary Links Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '20px' }}>
        
        {/* Dhan Broker Partner Consent Link */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px', border: '1px solid rgba(245, 158, 11, 0.4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '38px', height: '38px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-amber)' }}>
              <Link2 size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', margin: 0 }}>Dhan Broker Onboarding Consent</h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--accent-amber)' }}>Way 2 OAuth / Sub-Broker Binding</span>
            </div>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Direct your clients to bind their Dhan trading account under your partner code in 1-click without manual API key entry.
          </p>

          <div style={{ background: 'rgba(0, 0, 0, 0.4)', padding: '10px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <code className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {dhanPartnerUrl}
            </code>
            <button onClick={() => copyToClipboard(dhanPartnerUrl, 'dhan')} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>
              {copiedKey === 'dhan' ? <Check size={14} /> : <Copy size={14} />}
              <span>{copiedKey === 'dhan' ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        </div>

        {/* Standard Web Registration Referral Link */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px', border: '1px solid var(--border-highlight)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ width: '38px', height: '38px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-cyan)' }}>
              <Share2 size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', margin: 0 }}>Direct Web Referral URL</h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>Auto-fills Referral Code on Signup</span>
            </div>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Share this link across social media, webinars, or your website. All signups will automatically be attributed to you.
          </p>

          <div style={{ background: 'rgba(0, 0, 0, 0.4)', padding: '10px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <code className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {baseRefLink}
            </code>
            <button onClick={() => copyToClipboard(baseRefLink, 'base')} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>
              {copiedKey === 'base' ? <Check size={14} /> : <Copy size={14} />}
              <span>{copiedKey === 'base' ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* UTM Campaign Link Builder Card */}
      <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
          Custom UTM Campaign Link Builder
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
          Tag your traffic sources (e.g. YouTube, Telegram, WhatsApp, Website) to track conversion sources in analytics.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <div>
            <label>Campaign Source (utm_source)</label>
            <input
              type="text"
              value={campaignName}
              onChange={(e) => setCampaignName(e.target.value)}
              className="input-field"
              placeholder="e.g. telegram_channel, youtube_live"
            />
          </div>

          <div>
            <label>Campaign Medium (utm_medium)</label>
            <input
              type="text"
              value={campaignMedium}
              onChange={(e) => setCampaignMedium(e.target.value)}
              className="input-field"
              placeholder="e.g. social, direct_message, email"
            />
          </div>
        </div>

        <div style={{ background: 'rgba(0, 0, 0, 0.4)', padding: '12px 16px', borderRadius: '6px', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <code className="font-mono" style={{ fontSize: '0.85rem', color: 'var(--accent-amber)', wordBreak: 'break-all' }}>
            {customUtmLink}
          </code>
          <button onClick={() => copyToClipboard(customUtmLink, 'utm')} className="btn btn-amber" style={{ padding: '6px 14px', fontSize: '0.8rem' }}>
            {copiedKey === 'utm' ? <Check size={14} /> : <Copy size={14} />}
            <span>{copiedKey === 'utm' ? 'Copied' : 'Copy Campaign URL'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default MarketingLinksPage;
