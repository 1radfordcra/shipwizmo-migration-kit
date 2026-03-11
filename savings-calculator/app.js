// app.js — Broad Reach Shipping Savings Calculator

const CGI_BIN = "cgi-bin";

// ===== CHECKBOX TOGGLE STYLING =====
document.querySelectorAll('.checkbox-label input[type="checkbox"]').forEach(cb => {
  cb.addEventListener('change', function() {
    this.closest('.checkbox-label').classList.toggle('checked', this.checked);
  });
});

// ===== CARRIER RATE TABLES (2026) =====
// Rates reflect what high-volume shippers ACTUALLY pay — not retail.
// USPS: Commercial Plus pricing per Notice 123 (Jan 2026)
// UPS/FedEx: Published rates with ~25% negotiated volume discount applied
// DHL: Mid-market eCommerce contract rates
// All rates are zone-weighted averages (zones 2-5, typical DTC fulfillment).

// USPS Ground Advantage — Commercial Plus rates (Notice 123, zone-weighted avg)
const uspsRates = {
  domestic: { under1: 7.05, '1to2': 7.40, '2to5': 8.59, '5to10': 10.19 },
  canada:   { under1: 14.50, '1to2': 17.25, '2to5': 22.00, '5to10': 29.50 },
  international: { under1: 18.00, '1to2': 22.50, '2to5': 29.00, '5to10': 38.00 }
};

// UPS Ground — Heavily discounted account rates (~25% off published)
// These reflect what a mid-to-high volume shipper actually pays, not retail
const upsRates = {
  domestic: { under1: 8.45, '1to2': 9.20, '2to5': 10.85, '5to10': 14.50 },
  canada:   { under1: 18.00, '1to2': 21.50, '2to5': 27.00, '5to10': 35.00 },
  international: { under1: 24.00, '1to2': 29.00, '2to5': 36.00, '5to10': 45.00 }
};

// FedEx Ground/Home Delivery — Heavily discounted account rates (~25% off published)
// Reflects negotiated contract pricing, not walk-in retail rates
const fedexRates = {
  domestic: { under1: 9.10, '1to2': 9.85, '2to5': 11.99, '5to10': 15.75 },
  canada:   { under1: 19.50, '1to2': 23.00, '2to5': 28.50, '5to10': 37.00 },
  international: { under1: 25.50, '1to2': 30.50, '2to5': 38.00, '5to10': 48.00 }
};

// DHL eCommerce — mid-market contract rates
const dhlRates = {
  domestic: { under1: 7.50, '1to2': 8.25, '2to5': 9.75, '5to10': 13.00 },
  canada:   { under1: 12.00, '1to2': 15.00, '2to5': 19.50, '5to10': 26.00 },
  international: { under1: 15.00, '1to2': 19.00, '2to5': 25.00, '5to10': 33.00 }
};

// "Other" — average of all carriers as a baseline
const otherRates = {
  domestic: { under1: 8.00, '1to2': 8.70, '2to5': 10.30, '5to10': 13.35 },
  canada:   { under1: 16.00, '1to2': 19.20, '2to5': 24.25, '5to10': 31.90 },
  international: { under1: 20.60, '1to2': 25.25, '2to5': 32.00, '5to10': 41.00 }
};

// Broad Reach / Asendia — ultra-aggressive last-mile network rates
// Comparable to GoFo, UniUni, BPM-class pricing for lightweight parcels
const broadReachRates = {
  domestic: { under1: 2.15, '1to2': 2.85, '2to5': 3.75, '5to10': 5.25 },
  canada:   { under1: 3.50, '1to2': 4.50, '2to5': 6.25, '5to10': 9.00 },
  international: { under1: 5.75, '1to2': 7.25, '2to5': 9.50, '5to10': 13.50 }
};

const carrierRateMap = {
  'UPS': upsRates,
  'FedEx': fedexRates,
  'USPS': uspsRates,
  'DHL': dhlRates,
  'Other': otherRates
};

// ===== CALCULATE SAVINGS =====
function calculateSavings() {
  const volumeEl = document.getElementById('volume');
  const weightEl = document.getElementById('weight');
  const costEl = document.getElementById('costPerPkg');
  const carrierEl = document.getElementById('carrier');

  const volume = parseInt(volumeEl.value);
  const weight = weightEl.value;
  const userCost = parseFloat(costEl.value);
  const carrier = carrierEl.value;

  // Validation
  if (!volume || !weight) {
    const btn = document.getElementById('calcBtn');
    btn.style.animation = 'shake 400ms ease';
    setTimeout(() => btn.style.animation = '', 400);
    return;
  }

  // Get selected destinations
  const destinations = [];
  document.querySelectorAll('#destinations input[type="checkbox"]:checked').forEach(cb => {
    destinations.push(cb.value);
  });
  if (destinations.length === 0) {
    destinations.push('domestic');
  }

  // Determine the current carrier cost:
  // If user entered a custom cost, use that.
  // Otherwise, use the carrier's published rate from our tables.
  const carrierTable = carrierRateMap[carrier] || otherRates;
  let currentCost;
  if (!isNaN(userCost) && userCost > 0) {
    currentCost = userCost;
  } else {
    // Auto-fill from carrier rate table (blended across destinations)
    let totalCarrierRate = 0;
    destinations.forEach(dest => {
      totalCarrierRate += carrierTable[dest][weight];
    });
    currentCost = totalCarrierRate / destinations.length;
    // Show auto-filled rate in the input
    costEl.value = currentCost.toFixed(2);
  }

  // Calculate Broad Reach blended rate across selected destinations
  let totalBRRate = 0;
  destinations.forEach(dest => {
    totalBRRate += broadReachRates[dest][weight];
  });
  const avgBRRate = totalBRRate / destinations.length;

  // Also calculate what the carrier table says for comparison context
  let totalCarrierTableRate = 0;
  destinations.forEach(dest => {
    totalCarrierTableRate += carrierTable[dest][weight];
  });
  const avgCarrierTableRate = totalCarrierTableRate / destinations.length;

  // Calculate savings
  const perPkgSavings = Math.max(0, currentCost - avgBRRate);
  const monthlySavings = perPkgSavings * volume;
  const annualSavings = monthlySavings * 12;
  const savingsPct = currentCost > 0 ? (perPkgSavings / currentCost) * 100 : 0;

  const annualCurrentSpend = currentCost * volume * 12;
  const annualBRSpend = avgBRRate * volume * 12;

  // Show results
  const resultsEl = document.getElementById('results');
  resultsEl.setAttribute('aria-hidden', 'false');

  // Animate numbers
  animateValue('annualSavings', annualSavings, true);
  animateValue('monthlySavings', monthlySavings, true);
  animateValue('perPkgSavings', perPkgSavings, false, true);
  animateValue('savingsPct', savingsPct, false, false, true);

  // Update carrier label
  document.getElementById('carrierLabel').textContent = carrier;

  // Animate bars
  const maxSpend = annualCurrentSpend;
  const currentPct = 100;
  const brPct = maxSpend > 0 ? (annualBRSpend / maxSpend) * 100 : 0;

  setTimeout(() => {
    document.getElementById('barCurrent').style.width = currentPct + '%';
    document.getElementById('barCurrentLabel').textContent = formatCurrency(annualCurrentSpend) + '/yr';
    document.getElementById('barBR').style.width = brPct + '%';
    document.getElementById('barBRLabel').textContent = formatCurrency(annualBRSpend) + '/yr';
  }, 100);

  // Scroll to results
  setTimeout(() => {
    resultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 200);

  // Reveal trust section
  document.getElementById('trustSection').classList.add('visible');
}

// ===== ANIMATE NUMBER VALUES =====
function animateValue(elementId, targetValue, isCurrency, isDecimal, isPercent) {
  const el = document.getElementById(elementId);
  const duration = 800;
  const startTime = performance.now();
  const startValue = 0;

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = startValue + (targetValue - startValue) * eased;

    if (isPercent) {
      el.textContent = Math.round(current) + '%';
    } else if (isDecimal) {
      el.textContent = '$' + current.toFixed(2);
    } else if (isCurrency) {
      el.textContent = formatCurrency(current);
    }

    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }

  requestAnimationFrame(update);
}

// ===== FORMAT CURRENCY =====
function formatCurrency(value) {
  if (value >= 1000) {
    return '$' + Math.round(value).toLocaleString('en-US');
  }
  return '$' + value.toFixed(2);
}

// ===== MODAL =====
function openQuoteModal() {
  const modal = document.getElementById('quoteModal');
  modal.classList.add('active');
  document.getElementById('modalForm').style.display = '';
  document.getElementById('modalSuccess').style.display = 'none';
  document.body.style.overflow = 'hidden';

  // Focus first input
  setTimeout(() => {
    document.getElementById('qName').focus();
  }, 300);
}

function closeQuoteModal() {
  const modal = document.getElementById('quoteModal');
  modal.classList.remove('active');
  document.body.style.overflow = '';
}

async function submitQuoteForm() {
  const name = document.getElementById('qName').value.trim();
  const email = document.getElementById('qEmail').value.trim();
  const company = document.getElementById('qCompany').value.trim();
  const phone = document.getElementById('qPhone').value.trim();

  if (!name || !email || !company) {
    ['qName', 'qEmail', 'qCompany'].forEach(id => {
      const el = document.getElementById(id);
      if (!el.value.trim()) {
        el.style.borderColor = 'var(--color-error)';
        el.style.boxShadow = '0 0 0 3px rgba(248, 113, 113, 0.2)';
        setTimeout(() => {
          el.style.borderColor = '';
          el.style.boxShadow = '';
        }, 2000);
      }
    });
    return;
  }

  // Gather calculator context to pass along
  const volumeEl = document.getElementById('volume');
  const weightEl = document.getElementById('weight');
  const costEl = document.getElementById('costPerPkg');
  const carrierEl = document.getElementById('carrier');
  const destinations = [];
  document.querySelectorAll('#destinations input[type="checkbox"]:checked').forEach(cb => {
    destinations.push(cb.value);
  });
  const annualEl = document.getElementById('annualSavings');
  const pctEl = document.getElementById('savingsPct');

  const payload = {
    name,
    email,
    company,
    phone,
    carrier: carrierEl ? carrierEl.value : '',
    volume: volumeEl ? volumeEl.options[volumeEl.selectedIndex].text : '',
    weight: weightEl ? weightEl.options[weightEl.selectedIndex].text : '',
    destinations: destinations.join(', '),
    current_cost: costEl ? costEl.value : '',
    annual_savings: annualEl ? annualEl.textContent : '',
    savings_pct: pctEl ? pctEl.textContent : '',
  };

  // Disable button and show loading
  const submitBtn = document.querySelector('#modalForm .btn-cta');
  const originalText = submitBtn.textContent;
  submitBtn.textContent = 'Submitting...';
  submitBtn.disabled = true;
  submitBtn.style.opacity = '0.7';

  try {
    const res = await fetch(`${CGI_BIN}/quote.py`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.success) {
      document.getElementById('modalForm').style.display = 'none';
      document.getElementById('modalSuccess').style.display = '';
    } else {
      // Still show success to the visitor (don't expose CRM errors)
      // but log for debugging
      console.error('Quote API error:', data);
      document.getElementById('modalForm').style.display = 'none';
      document.getElementById('modalSuccess').style.display = '';
    }
  } catch (err) {
    console.error('Quote submission error:', err);
    // Graceful degradation — show success anyway so visitor isn't blocked
    document.getElementById('modalForm').style.display = 'none';
    document.getElementById('modalSuccess').style.display = '';
  }
}

// Close modal on overlay click
document.getElementById('quoteModal').addEventListener('click', function(e) {
  if (e.target === this) {
    closeQuoteModal();
  }
});

// Close modal on Escape
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeQuoteModal();
  }
});

// ===== SCROLL REVEAL =====
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.reveal').forEach(el => {
  revealObserver.observe(el);
});

// ===== SHAKE ANIMATION =====
const shakeStyle = document.createElement('style');
shakeStyle.textContent = `
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-6px); }
    40% { transform: translateX(6px); }
    60% { transform: translateX(-4px); }
    80% { transform: translateX(4px); }
  }
`;
document.head.appendChild(shakeStyle);
