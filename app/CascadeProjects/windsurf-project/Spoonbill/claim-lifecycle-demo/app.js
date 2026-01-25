const STAGES = {
    submitted: 'Claim Submitted',
    underwriting: 'Underwriting',
    funded: 'Funded',
    pending_settlement: 'Pending Settlement',
    settled: 'Settled / Reimbursed'
};

const STAGE_ORDER = ['submitted', 'underwriting', 'funded', 'pending_settlement', 'settled'];

const TOP_PAYERS = new Set(['Aetna', 'UnitedHealthcare', 'Cigna', 'BCBS', 'Humana']);

function formatMoneyUSD(n) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0
    }).format(n);
}

function stagePillClass(stage) {
    switch (stage) {
        case 'submitted':
            return { label: 'Submitted', cls: 'pill', dotCls: '' };
        case 'underwriting':
            return { label: 'Underwriting', cls: 'pill warn', dotCls: 'pill-dot' };
        case 'funded':
            return { label: 'Funded', cls: 'pill ok', dotCls: 'pill-dot' };
        case 'pending_settlement':
            return { label: 'Pending', cls: 'pill warn', dotCls: 'pill-dot' };
        case 'settled':
            return { label: 'Settled', cls: 'pill ok', dotCls: 'pill-dot' };
        default:
            return { label: stage, cls: 'pill', dotCls: 'pill-dot' };
    }
}

function computeUnderwritingDecision(claim) {
    const reasons = [];

    if (!TOP_PAYERS.has(claim.payer)) {
        reasons.push('Payer not in top 5');
    }

    if (claim.planType !== 'PPO') {
        reasons.push('Plan type not PPO');
    }

    if (claim.historicalPayRate < 0.85) {
        reasons.push('Historical pay rate < 85%');
    }

    if (claim.amount > 7500) {
        reasons.push('Amount exceeds $7,500');
    }

    const approved = reasons.length === 0;
    return {
        approved,
        status: approved ? 'Approved' : 'Declined',
        reasons: approved ? ['Meets underwriting rules'] : reasons
    };
}

function createInitialState() {
    return {
        capital: {
            total: 100000,
            available: 65000,
            allocated: 25000,
            pendingSettlement: 10000
        },
        selectedClaimId: null,
        claims: [
            {
                id: 'CLM-1001',
                practiceName: 'Bright Smiles Dental',
                amount: 4200,
                payer: 'Aetna',
                planType: 'PPO',
                procedure: 'D2740 Crown (Porcelain/Ceramic)',
                submittedAtDay: 0,
                daysOutstanding: 3,
                stage: 'submitted',
                underwriting: null,
                funding: { status: 'Not Funded', fundedAtDay: null },
                settlement: { status: 'Not Settled', settledAtDay: null }
            },
            {
                id: 'CLM-1002',
                practiceName: 'Lakeside Orthodontics',
                amount: 6900,
                payer: 'UnitedHealthcare',
                planType: 'PPO',
                procedure: 'D8080 Comprehensive Ortho',
                submittedAtDay: -2,
                daysOutstanding: 7,
                stage: 'underwriting',
                underwriting: null,
                funding: { status: 'Not Funded', fundedAtDay: null },
                settlement: { status: 'Not Settled', settledAtDay: null }
            },
            {
                id: 'CLM-1003',
                practiceName: 'Northside Family Practice',
                amount: 5100,
                payer: 'BCBS',
                planType: 'HMO',
                procedure: '99214 Office Visit',
                submittedAtDay: -4,
                daysOutstanding: 12,
                stage: 'underwriting',
                underwriting: null,
                funding: { status: 'Not Funded', fundedAtDay: null },
                settlement: { status: 'Not Settled', settledAtDay: null }
            },
            {
                id: 'CLM-1004',
                practiceName: 'Downtown Imaging Center',
                amount: 8500,
                payer: 'Cigna',
                planType: 'PPO',
                procedure: '72148 MRI Lumbar Spine',
                submittedAtDay: -7,
                daysOutstanding: 16,
                stage: 'submitted',
                underwriting: null,
                funding: { status: 'Not Funded', fundedAtDay: null },
                settlement: { status: 'Not Settled', settledAtDay: null }
            },
            {
                id: 'CLM-1005',
                practiceName: 'Sunrise Pediatrics',
                amount: 2500,
                payer: 'Humana',
                planType: 'PPO',
                procedure: '90471 Immunization Admin',
                submittedAtDay: -8,
                daysOutstanding: 21,
                stage: 'funded',
                underwriting: { approved: true, status: 'Approved', reasons: ['Meets underwriting rules'] },
                funding: { status: 'Funded', fundedAtDay: -6 },
                settlement: { status: 'Not Settled', settledAtDay: null }
            },
            {
                id: 'CLM-1006',
                practiceName: 'Coastal ENT',
                amount: 3100,
                payer: 'BCBS',
                planType: 'PPO',
                procedure: '31231 Nasal Endoscopy',
                submittedAtDay: -10,
                daysOutstanding: 27,
                stage: 'pending_settlement',
                underwriting: { approved: true, status: 'Approved', reasons: ['Meets underwriting rules'] },
                funding: { status: 'Funded', fundedAtDay: -9 },
                settlement: { status: 'Pending Settlement', settledAtDay: null }
            },
            {
                id: 'CLM-1007',
                practiceName: 'Green Valley Surgery',
                amount: 6000,
                payer: 'Aetna',
                planType: 'PPO',
                procedure: '29881 Knee Arthroscopy',
                submittedAtDay: -14,
                daysOutstanding: 35,
                stage: 'settled',
                underwriting: { approved: true, status: 'Approved', reasons: ['Meets underwriting rules'] },
                funding: { status: 'Funded', fundedAtDay: -13 },
                settlement: { status: 'Settled', settledAtDay: -2 }
            }
        ]
    };
}

function byStage(state, stage) {
    return state.claims
        .filter((c) => c.stage === stage)
        .slice()
        .sort((a, b) => a.daysOutstanding - b.daysOutstanding);
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function pill(label, kind) {
    const span = document.createElement('span');
    span.className = `pill ${kind ?? ''}`.trim();

    const dot = document.createElement('span');
    dot.className = 'pill-dot';
    span.appendChild(dot);

    const t = document.createElement('span');
    t.textContent = label;
    span.appendChild(t);

    return span;
}

function renderCapital(state) {
    setText('cap-total', formatMoneyUSD(state.capital.total));
    setText('cap-available', formatMoneyUSD(state.capital.available));
    setText('cap-allocated', formatMoneyUSD(state.capital.allocated));
    setText('cap-pending', formatMoneyUSD(state.capital.pendingSettlement));
}

function renderStage(state, stage) {
    const container = document.getElementById(`stage-${stage}`);
    if (!container) return;
    container.innerHTML = '';

    const claims = byStage(state, stage);
    if (claims.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'text-xs text-slate-400 px-2 py-3';
        empty.textContent = 'No claims in this stage';
        container.appendChild(empty);
        return;
    }

    for (const claim of claims) {
        const card = document.createElement('div');
        card.className = 'claim-card';
        card.tabIndex = 0;
        card.setAttribute('role', 'button');
        card.setAttribute('aria-label', `Claim ${claim.id}`);

        card.addEventListener('click', () => {
            state.selectedClaimId = claim.id;
            renderAll(state);
        });

        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                state.selectedClaimId = claim.id;
                renderAll(state);
            }
        });

        const top = document.createElement('div');
        top.className = 'claim-top';

        const left = document.createElement('div');
        left.className = 'claim-id';
        left.textContent = claim.id;

        const right = document.createElement('div');
        right.className = 'claim-amount';
        right.textContent = formatMoneyUSD(claim.amount);

        top.appendChild(left);
        top.appendChild(right);

        const meta = document.createElement('div');
        meta.className = 'claim-meta';

        const practice = document.createElement('div');
        practice.textContent = claim.practiceName;

        const more = document.createElement('div');
        more.className = 'flex items-center justify-between gap-2 text-[11px] text-slate-300';

        const days = document.createElement('span');
        days.textContent = `${claim.daysOutstanding} days outstanding`;

        const status = document.createElement('span');
        status.className = 'pill';

        const dot = document.createElement('span');
        dot.className = 'pill-dot';
        status.appendChild(dot);

        const label = document.createElement('span');

        if (stage === 'underwriting') {
            if (claim.underwriting?.approved === false) {
                status.className = 'pill bad';
                label.textContent = 'Declined';
            } else if (claim.underwriting?.approved === true) {
                status.className = claim.funding.status === 'Funded' ? 'pill ok' : 'pill warn';
                label.textContent = claim.funding.status === 'Funded' ? 'Approved' : 'Approved (Awaiting Capital)';
            } else {
                status.className = 'pill warn';
                label.textContent = 'Reviewing';
            }
        } else if (stage === 'funded') {
            status.className = 'pill ok';
            label.textContent = 'Funded';
        } else if (stage === 'pending_settlement') {
            status.className = 'pill warn';
            label.textContent = 'Pending';
        } else if (stage === 'settled') {
            status.className = 'pill ok';
            label.textContent = 'Settled';
        } else {
            status.className = 'pill';
            label.textContent = 'New';
        }

        status.appendChild(label);
        more.appendChild(days);
        more.appendChild(status);

        meta.appendChild(practice);
        meta.appendChild(more);

        card.appendChild(top);
        card.appendChild(meta);
        container.appendChild(card);
    }
}

function renderDetails(state) {
    const details = document.getElementById('details');
    const stagePill = document.getElementById('details-stage');
    if (!details || !stagePill) return;

    const claim = state.claims.find((c) => c.id === state.selectedClaimId);
    if (!claim) {
        stagePill.className = 'pill';
        stagePill.textContent = 'No claim selected';
        details.innerHTML = '<div class="text-sm text-slate-300">Click a claim card to view details.</div>';
        return;
    }

    const { label, cls } = stagePillClass(claim.stage);
    stagePill.className = cls;
    stagePill.innerHTML = '';

    const dot = document.createElement('span');
    dot.className = 'pill-dot';
    stagePill.appendChild(dot);
    const text = document.createElement('span');
    text.textContent = label;
    stagePill.appendChild(text);

    const uw = claim.underwriting ?? computeUnderwritingDecision(claim);
    const funded = claim.funding?.status ?? 'Not Funded';

    const grid = document.createElement('div');
    grid.className = 'detail-grid';

    const rows = [
        ['Claim ID', claim.id],
        ['Practice', claim.practiceName],
        ['Payer', claim.payer],
        ['Plan Type', claim.planType],
        ['Procedure', claim.procedure],
        ['Amount', formatMoneyUSD(claim.amount)],
        ['Days Outstanding', String(claim.daysOutstanding)],
        ['Underwriting Decision', uw.status],
        ['Underwriting Notes', uw.reasons.join(' • ')],
        ['Funding Status', funded],
        ['Settlement Status', claim.settlement?.status ?? 'Not Settled']
    ];

    for (const [k, v] of rows) {
        const row = document.createElement('div');
        row.className = 'detail-row';

        const key = document.createElement('div');
        key.className = 'detail-key';
        key.textContent = k;

        const val = document.createElement('div');
        val.className = 'detail-val';
        val.textContent = v;

        row.appendChild(key);
        row.appendChild(val);
        grid.appendChild(row);
    }

    details.innerHTML = '';
    details.appendChild(grid);
}

function normalizeCapital(state) {
    const cap = state.capital;
    const sum = cap.available + cap.allocated + cap.pendingSettlement;
    if (sum !== cap.total) {
        const delta = cap.total - sum;
        cap.available += delta;
    }
}

function advanceOneTick(state) {
    for (const claim of state.claims) {
        if (claim.stage !== 'settled') {
            claim.daysOutstanding += 2;
        }
    }

    for (const claim of state.claims) {
        if (claim.stage === 'submitted') {
            claim.stage = 'underwriting';
            continue;
        }

        if (claim.stage === 'underwriting') {
            if (!claim.underwriting) {
                claim.underwriting = computeUnderwritingDecision(claim);
            }

            if (!claim.underwriting.approved) {
                continue;
            }

            if (state.capital.available >= claim.amount) {
                state.capital.available -= claim.amount;
                state.capital.allocated += claim.amount;
                claim.funding = { status: 'Funded', fundedAtDay: claim.funding?.fundedAtDay ?? 0 };
                claim.stage = 'funded';
            } else {
                claim.funding = { status: 'Approved (Awaiting Capital)', fundedAtDay: null };
            }
            continue;
        }

        if (claim.stage === 'funded') {
            state.capital.allocated -= claim.amount;
            state.capital.pendingSettlement += claim.amount;
            claim.settlement = { status: 'Pending Settlement', settledAtDay: null };
            claim.stage = 'pending_settlement';
            continue;
        }

        if (claim.stage === 'pending_settlement') {
            state.capital.pendingSettlement -= claim.amount;
            state.capital.available += claim.amount;
            claim.settlement = { status: 'Settled', settledAtDay: 0 };
            claim.stage = 'settled';
            continue;
        }
    }

    normalizeCapital(state);
}

function renderAll(state) {
    renderCapital(state);
    for (const stage of STAGE_ORDER) {
        renderStage(state, stage);
    }
    renderDetails(state);
}

function mount() {
    let state = createInitialState();

    const advanceBtn = document.getElementById('advance');
    const resetBtn = document.getElementById('reset');

    advanceBtn?.addEventListener('click', () => {
        advanceOneTick(state);
        renderAll(state);
    });

    resetBtn?.addEventListener('click', () => {
        state = createInitialState();
        renderAll(state);
    });

    // Ensure underwriting is deterministic even if you click a claim before advancing
    for (const claim of state.claims) {
        if (claim.stage === 'underwriting' && !claim.underwriting) {
            claim.underwriting = computeUnderwritingDecision(claim);
        }
    }

    renderAll(state);
}

window.addEventListener('DOMContentLoaded', mount);
