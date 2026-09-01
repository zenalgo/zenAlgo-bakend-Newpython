import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 756, "ZenAlgo Strategy & Execution Platform — Developer API & Admin Tracing Reference")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.75)
            self.line(36, 750, letter[0] - 36, 750)
            
        # Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 36, 24, page_text)
        self.drawString(36, 24, "CONFIDENTIAL — FOR INTERNAL & FRONTEND DEVELOPMENT ONLY")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(36, 34, letter[0] - 36, 34)
        
        self.restoreState()


def build_pdf():
    pdf_path = "/Users/apple/.gemini/antigravity-ide/brain/4babdaee-ff45-4d48-be92-7ce7f90a0bf1/zenalgo_strategy_api_and_admin_tracing_docs.pdf"
    
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=44,
        bottomMargin=44
    )
    
    styles = getSampleStyleSheet()
    
    # Palette
    COLOR_PRIMARY = colors.HexColor("#0f172a")     # Slate 900
    COLOR_SECONDARY = colors.HexColor("#2563eb")   # Blue 600
    COLOR_ACCENT = colors.HexColor("#059669")      # Emerald 600
    COLOR_MUTED = colors.HexColor("#475569")       # Slate 600
    COLOR_BG_CODE = colors.HexColor("#f8fafc")     # Slate 50
    COLOR_BORDER = colors.HexColor("#cbd5e1")      # Slate 300
    COLOR_BOX_BG = colors.HexColor("#f1f5f9")      # Slate 100
    COLOR_WARN = colors.HexColor("#d97706")        # Amber 600
    COLOR_METHOD_POST = colors.HexColor("#16a34a") # Green
    COLOR_METHOD_GET = colors.HexColor("#2563eb")  # Blue
    COLOR_METHOD_PUT = colors.HexColor("#d97706")  # Amber
    COLOR_METHOD_DEL = colors.HexColor("#dc2626")  # Red

    # Typography Styles
    title_style = ParagraphStyle(
        name="DocTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=COLOR_PRIMARY,
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        name="DocSubtitle",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=COLOR_SECONDARY,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    meta_style = ParagraphStyle(
        name="MetaText",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=COLOR_MUTED,
        alignment=TA_CENTER
    )
    
    h1_style = ParagraphStyle(
        name="H1Custom",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        name="H2Custom",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=COLOR_SECONDARY,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        name="H3Custom",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=COLOR_PRIMARY,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        name="BodyCustom",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=COLOR_PRIMARY,
        spaceAfter=5
    )

    body_muted = ParagraphStyle(
        name="BodyMuted",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=COLOR_MUTED,
        spaceAfter=4
    )

    badge_post = ParagraphStyle(
        name="BadgePOST",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
        backColor=COLOR_METHOD_POST,
        borderPadding=3,
        alignment=TA_CENTER
    )

    endpoint_title = ParagraphStyle(
        name="EndpointTitle",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=COLOR_PRIMARY
    )

    code_style = ParagraphStyle(
        name="CodeBlock",
        fontName="Courier",
        fontSize=7.5,
        leading=9.5,
        textColor=COLOR_PRIMARY,
        backColor=COLOR_BG_CODE,
        borderColor=COLOR_BORDER,
        borderWidth=0.5,
        borderPadding=5,
        spaceAfter=6
    )

    table_cell = ParagraphStyle(
        name="TableCell",
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=COLOR_PRIMARY
    )

    table_cell_bold = ParagraphStyle(
        name="TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10.5,
        textColor=COLOR_PRIMARY
    )

    table_header = ParagraphStyle(
        name="TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10.5,
        textColor=colors.white
    )

    callout_box = ParagraphStyle(
        name="CalloutText",
        fontName="Helvetica",
        fontSize=8.2,
        leading=11.5,
        textColor=COLOR_PRIMARY
    )

    story = []

    # ==========================================
    # COVER / HEADER
    # ==========================================
    story.append(Paragraph("ZenAlgo Algorithmic Trading Platform", subtitle_style))
    story.append(Paragraph("STRATEGY API CONTRACT & ADMIN TRACING DOCUMENTATION", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Version:</b> 2.0.0 &nbsp;|&nbsp; <b>Execution Engine:</b> Event-Driven Quantitative Engine &nbsp;|&nbsp; <b>Default Mode:</b> PAPER", meta_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_SECONDARY, spaceBefore=2, spaceAfter=12))

    # Architecture Overview Callout Box
    arch_summary = (
        "<b>Executive Overview for Frontend Developers & Administrators:</b><br/>"
        "This API enables the full lifecycle of custom trading strategies. A single normalized JSON schema "
        "(Schema v2.0.0) powers all strategy archetypes: single-leg option buying (EMA Pullback, RSI Alert Candle) "
        "and 4-leg hedged option selling (Camarilla S3/R3 Pivot Reversal).<br/>"
        "<b>Pipeline:</b> Frontend JSON &#8594; Create (Dual Persistence) &#8594; Activate (Runtime State Machine) &#8594; "
        "Market Event &#8594; Strategy Engine &#8594; Golden Rules &#8594; Signal Engine &#8594; Risk Approval &#8594; "
        "Execution Validator &#8594; Execution Engine (PAPER/Mock) &#8594; Position Open &#8594; Exit Engine &#8594; Position Closed."
    )
    t_box = Table([[Paragraph(arch_summary, callout_box)]], colWidths=[540])
    t_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BOX_BG),
        ('BOX', (0, 0), (-1, -1), 1, COLOR_SECONDARY),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_box)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 1: STRATEGY LIFECYCLE & STATE MACHINE
    # ==========================================
    story.append(Paragraph("1. Strategy Lifecycle & State Machine Architecture", h1_style))
    story.append(Paragraph(
        "Every strategy operates strictly under a deterministic state machine managed by <code>StrategyStateManager</code>. "
        "The state controls what market events or exit checks the strategy is eligible to process.",
        body_style
    ))
    
    state_table_data = [
        [Paragraph("Lifecycle State", table_header), Paragraph("State Description", table_header), Paragraph("Allowed Next Transitions", table_header)],
        [Paragraph("<b>WAITING</b>", table_cell), Paragraph("Initial state after creation. Idle and un-activated.", table_cell), Paragraph("ELIGIBLE, ARCHIVED", table_cell)],
        [Paragraph("<b>ELIGIBLE</b>", table_cell), Paragraph("Validated and ready for scheduling / activation.", table_cell), Paragraph("MONITORING_ENTRY, PAUSED, WAITING", table_cell)],
        [Paragraph("<b>MONITORING_ENTRY</b>", table_cell), Paragraph("Active in Market Router. Receiving live candle/tick events to evaluate entry rules.", table_cell), Paragraph("ENTRY_SIGNAL, PAUSED, ELIGIBLE", table_cell)],
        [Paragraph("<b>ENTRY_SIGNAL</b>", table_cell), Paragraph("Entry condition matched & Golden Rules approved. Signal emitted to Risk Engine.", table_cell), Paragraph("ORDER_PENDING, MONITORING_ENTRY", table_cell)],
        [Paragraph("<b>ORDER_PENDING</b>", table_cell), Paragraph("Risk approved. Order dispatched to Execution Engine / Paper Broker.", table_cell), Paragraph("POSITION_OPEN, MONITORING_ENTRY", table_cell)],
        [Paragraph("<b>POSITION_OPEN</b>", table_cell), Paragraph("Paper order filled. User position opened and tracked in database.", table_cell), Paragraph("MONITORING_EXIT, EXIT_ORDER_PENDING", table_cell)],
        [Paragraph("<b>MONITORING_EXIT</b>", table_cell), Paragraph("ExitEngine actively evaluating targets, stop loss, trailing stops, or 15:15 square-off.", table_cell), Paragraph("EXIT_SIGNAL, EXIT_ORDER_PENDING", table_cell)],
        [Paragraph("<b>EXIT_SIGNAL</b>", table_cell), Paragraph("Exit condition triggered. EXIT signal emitted to Execution Engine.", table_cell), Paragraph("EXIT_ORDER_PENDING, POSITION_OPEN", table_cell)],
        [Paragraph("<b>EXIT_ORDER_PENDING</b>", table_cell), Paragraph("Exit square-off order executing at broker.", table_cell), Paragraph("POSITION_CLOSED, POSITION_OPEN", table_cell)],
        [Paragraph("<b>POSITION_CLOSED</b>", table_cell), Paragraph("All legs closed and reconciled. Returns to MONITORING_ENTRY if re-entry allowed.", table_cell), Paragraph("MONITORING_ENTRY, ELIGIBLE, WAITING", table_cell)],
        [Paragraph("<b>PAUSED / ARCHIVED</b>", table_cell), Paragraph("Manually paused by user or archived. Detached from market data router.", table_cell), Paragraph("ELIGIBLE, WAITING, MONITORING_ENTRY", table_cell)],
    ]
    t_states = Table(state_table_data, colWidths=[120, 240, 180])
    t_states.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_CODE]),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_states)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 2: ENDPOINT 1: CREATE STRATEGY
    # ==========================================
    story.append(Paragraph("2. Endpoint Reference: Strategy Management", h1_style))
    
    # Endpoint 1 Card
    ep1_head = [
        [Paragraph("<b>POST</b>", badge_post), Paragraph("<b>/api/strategy</b> &nbsp; <i>(Canonical)</i> &nbsp; or &nbsp; <b>/api/v1/strategies</b>", endpoint_title)]
    ]
    t_ep1_head = Table(ep1_head, colWidths=[60, 480])
    t_ep1_head.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_ep1_head)
    story.append(Spacer(1, 4))
    
    story.append(Paragraph(
        "<b>Why We Use This API:</b> This is the primary entry point for frontend strategy creation. "
        "It accepts Schema Version 2.0.0 JSON payloads, performs pre-flight validation, creates the Strategy root entity, "
        "creates an immutable <code>StrategyVersion</code> (v1), persists relational legs/settings, serializes all rich builder fields into parameters JSON, "
        "and initializes the <code>StrategyRuntimeState</code> in <code>WAITING</code> state.",
        body_style
    ))

    story.append(Paragraph("<b>Authentication & Headers:</b>", h3_style))
    story.append(Paragraph("<code>Authorization: Bearer &lt;JWT_TOKEN&gt;</code> &nbsp;|&nbsp; <code>Content-Type: application/json</code>", code_style))

    story.append(Paragraph("<b>Key Request Fields (Schema v2.0.0):</b>", h3_style))
    req_fields_data = [
        [Paragraph("Field", table_header), Paragraph("Type", table_header), Paragraph("Required", table_header), Paragraph("Description & Notes", table_header)],
        [Paragraph("<code>schemaVersion</code>", table_cell), Paragraph("string", table_cell), Paragraph("Yes", table_cell), Paragraph("Must be <code>\"2.0.0\"</code>.", table_cell)],
        [Paragraph("<code>meta</code>", table_cell), Paragraph("object", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>{ strategyId, strategyName, authorName, status }</code>.", table_cell)],
        [Paragraph("<code>tradingHorizon</code>", table_cell), Paragraph("string", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>\"Intraday\"</code>, <code>\"Monthly\"</code>, or <code>\"Positional\"</code>.", table_cell)],
        [Paragraph("<code>timeframe</code>", table_cell), Paragraph("string", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>\"5m\"</code>, <code>\"15m\"</code>, <code>\"1h\"</code>, <code>\"Daily\"</code> / <code>\"1d\"</code>.", table_cell)],
        [Paragraph("<code>instrument</code>", table_cell), Paragraph("object", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>{ underlying: \"NIFTY 50\"|\"RELIANCE\", expiryType: \"Weekly\"|\"Monthly\" }</code>.", table_cell)],
        [Paragraph("<code>schedule</code>", table_cell), Paragraph("object", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>{ entryFrom: \"09:30\", forcedExitTime: \"15:15\", applicableDays }</code>.", table_cell)],
        [Paragraph("<code>entryConditions</code>", table_cell), Paragraph("array", table_cell), Paragraph("Yes", table_cell), Paragraph("List of indicator / price / candlestick rules (e.g. EMA 8 > EMA 33, RSI > 60).", table_cell)],
        [Paragraph("<code>exitConditions</code>", table_cell), Paragraph("array", table_cell), Paragraph("Yes", table_cell), Paragraph("List of exit rules (Target 2R, SL hit, opposite crossover, 15:15 forced exit).", table_cell)],
        [Paragraph("<code>riskManagement</code>", table_cell), Paragraph("object", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>{ maxLossPerTrade, maxLossPerDay, maxLossPerWeek, maxTradesPerDay, stopLoss }</code>.", table_cell)],
        [Paragraph("<code>target</code>", table_cell), Paragraph("object", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>{ value: \"2R\"|\"Alert Candle Range\"|\"2.5%\", targets }</code>.", table_cell)],
        [Paragraph("<code>options</code>", table_cell), Paragraph("object", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>{ strikeSelection: \"ATM\", legs: [...] }</code>. Contains 4 legs for multi-leg.", table_cell)],
        [Paragraph("<code>execution</code>", table_cell), Paragraph("object", table_cell), Paragraph("Yes", table_cell), Paragraph("<code>{ orderType: \"MARKET\"|\"LIMIT\", slippage: 0.10, orderTimeout: 30 }</code>.", table_cell)],
        [Paragraph("<code>mode</code>", table_cell), Paragraph("string", table_cell), Paragraph("No", table_cell), Paragraph("Defaults to <code>\"PAPER\"</code>. Live mode protected.", table_cell)],
    ]
    t_req = Table(req_fields_data, colWidths=[100, 50, 45, 345])
    t_req.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_CODE]),
        ('PADDING', (0, 0), (-1, -1), 3.5),
    ]))
    story.append(t_req)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>cURL Example:</b>", h3_style))
    curl_create = (
        'curl -X POST "https://api.zenalgo.com/api/strategy" \\\n'
        '  -H "Authorization: Bearer YOUR_JWT_TOKEN" \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{\n'
        '    "schemaVersion": "2.0.0",\n'
        '    "meta": {"strategyId": "EMA_8_33_PULLBACK", "strategyName": "Nifty EMA 8/33 Scalper"},\n'
        '    "tradingHorizon": "Intraday",\n'
        '    "timeframe": "5m",\n'
        '    "instrument": {"underlying": "NIFTY 50", "expiryType": "Weekly"},\n'
        '    "schedule": {"entryFrom": "09:30", "forcedExitTime": "15:15"},\n'
        '    "entryConditions": ["8 EMA crosses above 33 EMA", "Pullback to 8 EMA"],\n'
        '    "riskManagement": {"maxLossPerTrade": 2500.0, "riskRewardRatio": "1:2"},\n'
        '    "target": {"value": "2R"},\n'
        '    "options": {"strikeSelection": "ATM"},\n'
        '    "execution": {"orderType": "MARKET"}\n'
        '  }\''
    )
    story.append(Paragraph(curl_create.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style))

    story.append(Paragraph("<b>Response Example (201 Created):</b>", h3_style))
    resp_create = (
        '{\n'
        '  "success": true,\n'
        '  "message": "Strategy created successfully",\n'
        '  "data": {\n'
        '    "id": 1042,\n'
        '    "currentVersionId": 2085,\n'
        '    "name": "Nifty EMA 8/33 Scalper",\n'
        '    "status": "DRAFT",\n'
        '    "mode": "PAPER",\n'
        '    "timeframe": "5m",\n'
        '    "underlying": "NIFTY",\n'
        '    "capital": "100000.00",\n'
        '    "legs": [{"sequence": 1, "segment": "OPT", "side": "BUY", "strikeSelection": "ATM"}],\n'
        '    "schedule": {"entryFrom": "09:30", "forcedExitTime": "15:15"}\n'
        '  }\n'
        '}'
    )
    story.append(Paragraph(resp_create.replace('\n', '<br/>').replace(' ', '&nbsp;'), code_style))
    story.append(Spacer(1, 10))

    # ==========================================
    # SECTION 3: ENDPOINT 2: GET STRATEGY & ROUND-TRIP
    # ==========================================
    ep2_head = [
        [Paragraph("<b>GET</b>", ParagraphStyle("BGet", parent=badge_post, backColor=COLOR_METHOD_GET)), Paragraph("<b>/api/strategy/{id}</b> &nbsp; or &nbsp; <b>/api/v1/strategies/{id}</b>", endpoint_title)]
    ]
    t_ep2_head = Table(ep2_head, colWidths=[60, 480])
    t_ep2_head.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('PADDING', (0, 0), (-1, -1), 2)]))
    story.append(t_ep2_head)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Why We Use This API:</b> Used by the frontend builder to reload the full strategy configuration when viewing, "
        "editing, or analyzing backtest/paper results. It deserializes and returns all original builder fields (including 4-leg option definitions, "
        "pivot configuration, earnings exclusion, risk limits, and trailing stops) exactly as sent during creation.",
        body_style
    ))
    story.append(Paragraph("<b>cURL Example:</b>", h3_style))
    story.append(Paragraph('curl -X GET "https://api.zenalgo.com/api/strategy/1042" -H "Authorization: Bearer YOUR_JWT_TOKEN"', code_style))
    story.append(Spacer(1, 10))

    # ==========================================
    # SECTION 4: ENDPOINT 3: ACTIVATE STRATEGY
    # ==========================================
    ep3_head = [
        [Paragraph("<b>POST</b>", badge_post), Paragraph("<b>/api/strategy/{id}/activate</b> &nbsp; or &nbsp; <b>/api/v1/strategies/{id}/activate</b>", endpoint_title)]
    ]
    t_ep3_head = Table(ep3_head, colWidths=[60, 480])
    t_ep3_head.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('PADDING', (0, 0), (-1, -1), 2)]))
    story.append(t_ep3_head)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>Why We Use This API:</b> Activates a strategy for autonomous paper trading. It validates strategy completeness, "
        "transitions runtime state from <code>WAITING</code> &#8594; <code>ELIGIBLE</code> &#8594; <code>MONITORING_ENTRY</code>, "
        "and dynamically registers the strategy with <code>StrategyRouter</code> to start processing live market tick/candle events. "
        "<b>Idempotent:</b> Activating an already active strategy is safe and returns the active strategy state.",
        body_style
    ))
    story.append(Paragraph("<b>cURL Example:</b>", h3_style))
    story.append(Paragraph('curl -X POST "https://api.zenalgo.com/api/strategy/1042/activate" -H "Authorization: Bearer YOUR_JWT_TOKEN"', code_style))
    story.append(Spacer(1, 12))

    # ==========================================
    # SECTION 5: ADMIN OBSERVABILITY & TRACING ARCHITECTURE
    # ==========================================
    story.append(PageBreak())
    story.append(Paragraph("3. Admin Observability & End-to-End Tracing Architecture", h1_style))
    story.append(Paragraph(
        "For compliance, debugging, copy-trading management, and financial auditability, the system records a complete, "
        "immutable correlation chain across all domain layers. Administrators can trace every order and fill back to the exact candle, "
        "market event key, strategy version, and risk approval trace.",
        body_style
    ))

    trace_map_data = [
        [Paragraph("Tracing Field", table_header), Paragraph("Originating Domain", table_header), Paragraph("Format / Example", table_header), Paragraph("Audit Purpose", table_header)],
        [Paragraph("<code>strategy_id</code>", table_cell_bold), Paragraph("Strategy Domain", table_cell), Paragraph("<code>1042</code>", table_cell), Paragraph("Identifies the user's root strategy entity.", table_cell)],
        [Paragraph("<code>strategy_version_id</code>", table_cell_bold), Paragraph("Strategy Domain", table_cell), Paragraph("<code>2085</code>", table_cell), Paragraph("Guarantees immutability. Trades execute on the exact version configured.", table_cell)],
        [Paragraph("<code>market_event_key</code>", table_cell_bold), Paragraph("Market Data", table_cell), Paragraph("<code>1042:NIFTY:5m:2026-09-01T09:35:00</code>", table_cell), Paragraph("Ensures exactly-once processing per candle/tick event.", table_cell)],
        [Paragraph("<code>signal_key</code>", table_cell_bold), Paragraph("Signal Engine", table_cell), Paragraph("<code>SIG-ENTRY-1042-2085-20260901-0935</code>", table_cell), Paragraph("Deterministic signal key preventing duplicate trade triggers.", table_cell)],
        [Paragraph("<code>execution_batch_id</code>", table_cell_bold), Paragraph("Signal Domain", table_cell), Paragraph("<code>5501</code>", table_cell), Paragraph("Groups all copy-trading users associated with a signal.", table_cell)],
        [Paragraph("<code>correlation_id</code>", table_cell_bold), Paragraph("Risk & Execution", table_cell), Paragraph("<code>TRACE-5501-1042-USR-88-a1b2c3d4</code>", table_cell), Paragraph("Unique end-to-end trace per user execution.", table_cell)],
        [Paragraph("<code>execution_id</code>", table_cell_bold), Paragraph("Execution Engine", table_cell), Paragraph("<code>7742</code>", table_cell), Paragraph("Persisted execution record linking to filled broker orders.", table_cell)],
        [Paragraph("<code>position_id</code>", table_cell_bold), Paragraph("Position Tracker", table_cell), Paragraph("<code>9903</code>", table_cell), Paragraph("Active open position with real-time net quantity & PnL.", table_cell)],
        [Paragraph("<code>exit_signal_key</code>", table_cell_bold), Paragraph("Exit Engine", table_cell), Paragraph("<code>SIG-EXIT-1042-9903-TARGET-2R</code>", table_cell), Paragraph("Exit condition record (Target 2R, Stop Loss, or 15:15 square-off).", table_cell)],
    ]
    t_trace = Table(trace_map_data, colWidths=[110, 85, 160, 185])
    t_trace.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_CODE]),
        ('PADDING', (0, 0), (-1, -1), 3.5),
    ]))
    story.append(t_trace)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 6: ADMIN API ENDPOINTS
    # ==========================================
    story.append(Paragraph("4. Admin Strategy & Audit Endpoints", h1_style))

    admin_endpoints = [
        [Paragraph("HTTP Method & Route", table_header), Paragraph("Role Required", table_header), Paragraph("Purpose & Functionality", table_header)],
        [Paragraph("<b>GET</b> <code>/api/v1/admin/strategies</code>", table_cell), Paragraph("SUPER_ADMIN, ADMIN", table_cell), Paragraph("Query all system strategies with user filter, status filter, and pagination.", table_cell)],
        [Paragraph("<b>GET</b> <code>/api/v1/admin/strategies/{id}</code>", table_cell), Paragraph("SUPER_ADMIN, ADMIN", table_cell), Paragraph("Fetch detailed strategy configuration, execution logs, and runtime state.", table_cell)],
        [Paragraph("<b>POST</b> <code>/api/v1/admin/strategies</code>", table_cell), Paragraph("SUPER_ADMIN, ADMIN", table_cell), Paragraph("Admin-level strategy creation and provisioning on behalf of users.", table_cell)],
        [Paragraph("<b>POST</b> <code>/api/v1/admin/strategies/{id}/activate-paper</code>", table_cell), Paragraph("SUPER_ADMIN, ADMIN", table_cell), Paragraph("Admin override to activate any user strategy directly into PAPER trading.", table_cell)],
        [Paragraph("<b>POST</b> <code>/api/v1/admin/strategies/{id}/activate-live</code>", table_cell), Paragraph("SUPER_ADMIN", table_cell), Paragraph("Protected live activation switch. Requires environment production flag and broker approval.", table_cell)],
    ]
    t_admin_ep = Table(admin_endpoints, colWidths=[170, 100, 270])
    t_admin_ep.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_CODE]),
        ('PADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_admin_ep)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 7: 3 AUTHORITATIVE STRATEGY ARCHETYPES
    # ==========================================
    story.append(Paragraph("5. Supported Reference Strategy Archetypes (Payload Matrix)", h1_style))
    
    strat_matrix = [
        [Paragraph("Strategy Name", table_header), Paragraph("Archetype", table_header), Paragraph("Underlying / TF", table_header), Paragraph("Leg Structure & Execution", table_header), Paragraph("Exit Rules", table_header)],
        [
            Paragraph("<b>Strategy 1</b><br/><code>EMA_8_33_PULLBACK</code>", table_cell),
            Paragraph("Trend Following<br/>Option Buying", table_cell),
            Paragraph("NIFTY 50<br/>5m timeframe<br/>Weekly Expiry", table_cell),
            Paragraph("Single-leg dynamically resolved <b>ATM BUY CE / PE</b>. Market order, 0.10% slippage.", table_cell),
            Paragraph("Target = 2R.<br/>SL = Confirmation candle low/high.<br/>50% partial exit at 1R.<br/>Forced exit = 15:15.", table_cell)
        ],
        [
            Paragraph("<b>Strategy 2</b><br/><code>RSI_60_ALERT_CANDLE</code>", table_cell),
            Paragraph("Momentum Breakout<br/>Option Buying", table_cell),
            Paragraph("NIFTY 50<br/>15m timeframe<br/>Weekly Expiry", table_cell),
            Paragraph("Single-leg <b>ATM BUY CE</b> on alert candle high breach / <b>BUY PE</b> on low breach.", table_cell),
            Paragraph("Target = Alert Candle Range.<br/>SL = Alert candle low/high.<br/>Trailing stop enabled.<br/>Forced exit = 15:15.", table_cell)
        ],
        [
            Paragraph("<b>Strategy 3</b><br/><code>RELIANCE_S3_R3_PIVOT_REVERSAL</code>", table_cell),
            Paragraph("Mean Reversion<br/>Option Selling (Hedged)", table_cell),
            Paragraph("RELIANCE<br/>Daily timeframe<br/>Monthly Expiry", table_cell),
            Paragraph("<b>ALL 4 LEGS PRESERVED:</b><br/>• Leg 1: SELL CE (ATM)<br/>• Leg 2: BUY CE (+200pt Hedge)<br/>• Leg 3: SELL PE (ATM)<br/>• Leg 4: BUY PE (-200pt Hedge)", table_cell),
            Paragraph("Target = 2.5% Premium Decay.<br/>SL = R3/S3 breach.<br/>Quarterly earnings excluded.<br/>Simultaneous 4-leg square-off.", table_cell)
        ],
    ]
    t_matrix = Table(strat_matrix, colWidths=[105, 95, 85, 140, 115])
    t_matrix.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_CODE]),
        ('PADDING', (0, 0), (-1, -1), 3.5),
    ]))
    story.append(t_matrix)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 8: ERROR HANDLING & CODES
    # ==========================================
    story.append(Paragraph("6. Standard Error Codes & Validation Rules", h1_style))
    err_data = [
        [Paragraph("Error Code", table_header), Paragraph("HTTP Status", table_header), Paragraph("Root Cause", table_header), Paragraph("Resolution / Action", table_header)],
        [Paragraph("<code>TIME_REQUIRED</code>", table_cell), Paragraph("400", table_cell), Paragraph("Schedule time format is missing or invalid.", table_cell), Paragraph("Provide time in HH:MM format (e.g. \"09:30\").", table_cell)],
        [Paragraph("<code>INVALID_UNDERLYING</code>", table_cell), Paragraph("400", table_cell), Paragraph("Underlying not in supported list.", table_cell), Paragraph("Use NIFTY, BANKNIFTY, FINNIFTY, RELIANCE, TCS, etc.", table_cell)],
        [Paragraph("<code>INVALID_EXECUTION_PACKAGE</code>", table_cell), Paragraph("422", table_cell), Paragraph("Short option leg missing mandatory hedge leg.", table_cell), Paragraph("Ensure multi-leg option selling includes protective BUY leg.", table_cell)],
        [Paragraph("<code>EXECUTION_DUPLICATE</code>", table_cell), Paragraph("409", table_cell), Paragraph("Execution request already processed for signal.", table_cell), Paragraph("Ignored safely by idempotency boundary.", table_cell)],
        [Paragraph("<code>RISK_LIMIT_EXCEEDED</code>", table_cell), Paragraph("422", table_cell), Paragraph("Daily trade count or max loss threshold exceeded.", table_cell), Paragraph("Strategy enters cooldown or halts for the trading session.", table_cell)],
    ]
    t_err = Table(err_data, colWidths=[130, 60, 160, 190])
    t_err.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_CODE]),
        ('PADDING', (0, 0), (-1, -1), 3.5),
    ]))
    story.append(t_err)
    
    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF at: {pdf_path}")

if __name__ == "__main__":
    build_pdf()
