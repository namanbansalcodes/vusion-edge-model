import { useState, useEffect, useCallback, useRef } from "react";

const speak = (text, urgent = false) => {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = urgent ? 1.15 : 1.0;
  u.pitch = urgent ? 1.2 : 1.0;
  u.volume = 1;
  const voices = window.speechSynthesis.getVoices();
  const pref = voices.find(v => v.name.includes("Google") || v.name.includes("Daniel") || v.name.includes("Samantha"));
  if (pref) u.voice = pref;
  window.speechSynthesis.speak(u);
  return u;
};

const INVENTORY_DB = {
  "pasta-barilla": { sku: "pasta-barilla", name: "Barilla Pasta", aisle: 3, row_num: 2, backroom_qty: 24, shelf_qty: 0, vendor_name: "Barilla Direct", vendor_phone: "+1-800-922-7455", reorder_threshold: 5, unit_cost: 1.89 },
  "milk-whole": { sku: "milk-whole", name: "Whole Milk 1gal", aisle: 1, row_num: 1, backroom_qty: 0, shelf_qty: 2, vendor_name: "DairyFresh Co", vendor_phone: "+1-800-555-0199", reorder_threshold: 10, unit_cost: 3.49 },
  "bread-wonder": { sku: "bread-wonder", name: "Wonder Bread", aisle: 2, row_num: 3, backroom_qty: 12, shelf_qty: 1, vendor_name: "Wonder Bakery", vendor_phone: "+1-800-555-0342", reorder_threshold: 8, unit_cost: 2.99 },
  "chips-lays": { sku: "chips-lays", name: "Lay's Classic", aisle: 4, row_num: 1, backroom_qty: 0, shelf_qty: 0, vendor_name: "Frito-Lay Dist.", vendor_phone: "+1-800-555-0777", reorder_threshold: 15, unit_cost: 4.29 },
  "yogurt-greek": { sku: "yogurt-greek", name: "Greek Yogurt", aisle: 1, row_num: 3, backroom_qty: 36, shelf_qty: 4, vendor_name: "Chobani Supply", vendor_phone: "+1-800-555-0488", reorder_threshold: 12, unit_cost: 5.99 },
  "cereal-cheerios": { sku: "cereal-cheerios", name: "Cheerios", aisle: 5, row_num: 2, backroom_qty: 8, shelf_qty: 3, vendor_name: "General Mills", vendor_phone: "+1-800-555-0621", reorder_threshold: 6, unit_cost: 4.49 },
};

const INIT_WORKERS = [
  { id: "W1", name: "Marcus", zone: "Aisles 1-2", status: "available" },
  { id: "W2", name: "Priya", zone: "Aisles 3-4", status: "available" },
  { id: "W3", name: "James", zone: "Aisles 5-6", status: "available" },
  { id: "W4", name: "Sofia", zone: "Cleaning", status: "available" },
];

const VISION_EVENTS = [
  { type: "stockout", camera: "CAM-03", description: "Aisle 3, Row 2: Pasta shelf completely empty.", product_sku: "pasta-barilla", confidence: 0.94 },
  { type: "fridge_open", camera: "CAM-01", description: "Dairy fridge door open — left-side, ~45° angle, >30s.", aisle: 1, side: "left", confidence: 0.98 },
  { type: "misalignment", camera: "CAM-04", description: "Aisle 4, Row 1: Chips bags fallen, 3 items wrong direction.", product_sku: "chips-lays", confidence: 0.87 },
  { type: "hygiene", camera: "CAM-02", description: "Aisle 2, Row 3: Brown liquid stain ~15cm on shelf.", aisle: 2, row: 3, confidence: 0.91 },
  { type: "stockout", camera: "CAM-01", description: "Aisle 1, Row 1: Milk section only 2 units. Below threshold.", product_sku: "milk-whole", confidence: 0.89 },
  { type: "misalignment", camera: "CAM-05", description: "Aisle 5, Row 2: Cereal boxes pushed back, front gap.", product_sku: "cereal-cheerios", confidence: 0.85 },
  { type: "hygiene", camera: "CAM-01", description: "Aisle 1, Row 3: Yogurt residue on shelf edge.", aisle: 1, row: 3, confidence: 0.88 },
  { type: "stockout", camera: "CAM-04", description: "Aisle 4, Row 1: Chips fully depleted. Shelf bare.", product_sku: "chips-lays", confidence: 0.96 },
];

const ICONS = { stockout: "\u{1F4E6}", fridge_open: "\u{1F9CA}", misalignment: "\u{2194}\u{FE0F}", hygiene: "\u{1F9F9}" };
const PRIO = { fridge_open: "CRITICAL", stockout: "HIGH", hygiene: "MEDIUM", misalignment: "LOW" };
const PRIO_CLR = { CRITICAL: "#ef4444", HIGH: "#f97316", MEDIUM: "#eab308", LOW: "#3b82f6" };
const STAT_CLR = { open: "#ef4444", assigned: "#f97316", in_progress: "#eab308", resolved: "#22c55e", ordered: "#8b5cf6", calling: "#ec4899" };
const SLA = { CRITICAL: 2, HIGH: 15, MEDIUM: 10, LOW: 30 };

let tktSeq = 0;

const Badge = ({ color, children }) => (
  <span style={{ background: color + "20", color, border: "1px solid " + color + "55", borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 700 }}>{children}</span>
);

const Card = ({ children, style, onClick }) => (
  <div onClick={onClick} style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 12, padding: 16, ...style }}>{children}</div>
);

export default function ManagerDashboard() {
  const [inventory] = useState(JSON.parse(JSON.stringify(INVENTORY_DB)));
  const [workers, setWorkers] = useState(JSON.parse(JSON.stringify(INIT_WORKERS)));
  const [tickets, setTickets] = useState([]);
  const [actionLog, setActionLog] = useState([]);
  const [visionLog, setVisionLog] = useState([]);
  const [vendorOrders, setVendorOrders] = useState([]);
  const [eventIdx, setEventIdx] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [tab, setTab] = useState("dashboard");
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const [callInProgress, setCallInProgress] = useState(null);
  const [speakingNow, setSpeakingNow] = useState(null);
  const logRef = useRef(null);

  const agentSpeak = useCallback((text, urgent = false) => {
    if (!ttsEnabled) return;
    setSpeakingNow(text);
    const u = speak(text, urgent);
    if (u) u.onend = () => setSpeakingNow(null);
    else setTimeout(() => setSpeakingNow(null), 3000);
  }, [ttsEnabled]);

  const findWorker = useCallback((aisle, role) => {
    if (role) return workers.find(w => w.status === "available" && w.zone.includes(role)) || workers.find(w => w.status === "available");
    if (aisle) {
      const lo = aisle - (aisle % 2);
      const zoneStr = "Aisles " + lo + "-" + (lo + 1);
      return workers.find(w => w.status === "available" && w.zone === zoneStr) || workers.find(w => w.status === "available");
    }
    return workers.find(w => w.status === "available");
  }, [workers]);

  const processEvent = useCallback((event) => {
    const now = new Date().toLocaleTimeString();
    const t0 = performance.now();
    const ticketId = "TKT-" + String(++tktSeq).padStart(4, "0");
    const priority = PRIO[event.type];
    const sla = SLA[priority];
    const acts = [];

    setVisionLog(prev => [...prev, { ...event, timestamp: now }]);

    if (event.type === "stockout") {
      const item = inventory[event.product_sku];
      if (!item) return;

      if (item.backroom_qty > 0) {
        const w = findWorker(item.aisle, null);
        const wn = w ? w.name : "Any worker";
        const msg = "Attention " + wn + ". Aisle " + item.aisle + ", " + item.name + " shelf is empty. Backroom has " + item.backroom_qty + " units. Please restock within " + sla + " minutes.";
        agentSpeak(msg);
        if (w) setWorkers(prev => prev.map(x => x.id === w.id ? { ...x, status: "busy" } : x));
        setTickets(prev => [...prev, { ticketId, type: "restock", priority, status: "assigned", assignee: wn, product: item.name, sku: event.product_sku, location: "Aisle " + item.aisle + ", Row " + item.row_num, sla, createdAt: new Date() }]);
        acts.push({
          action: "radio_announce", message: "Radio: " + msg, timestamp: now,
          modelTrace: 'query_inventory("' + event.product_sku + '")\n  -> backroom_qty: ' + item.backroom_qty + ' > 0\n  -> assign_worker(task="restock", aisle=' + item.aisle + ', priority="HIGH")\n  -> create_ticket(type="restock")'
        });
      } else {
        const qty = item.reorder_threshold * 3;
        const cost = (item.unit_cost * qty).toFixed(2);
        const msg = "Manager, approval needed. " + item.name + " is completely out of stock, shelf and backroom both empty. Recommending order of " + qty + " units from " + item.vendor_name + " at $" + cost + " total. Please approve on the dashboard.";
        agentSpeak(msg);
        setTickets(prev => [...prev, { ticketId, type: "vendor_order", priority, status: "open", assignee: "Pending Manager", product: item.name, sku: event.product_sku, location: "Aisle " + item.aisle + ", Row " + item.row_num, sla: 240, vendor: item.vendor_name, vendorPhone: item.vendor_phone, orderQty: qty, orderCost: cost, approved: false, createdAt: new Date() }]);
        setVendorOrders(prev => [...prev, { ticketId, vendor: item.vendor_name, vendorPhone: item.vendor_phone, product: item.name, sku: event.product_sku, qty, cost, status: "pending_approval" }]);
        acts.push({
          action: "manager_approval_needed", message: "Alert: " + msg, timestamp: now,
          modelTrace: 'query_inventory("' + event.product_sku + '")\n  -> backroom_qty: 0, shelf_qty: ' + item.shelf_qty + '\n  -> request_vendor_order(vendor="' + item.vendor_name + '", qty=' + qty + ')\n  -> escalate_to_manager(severity="warning")'
        });
      }
    } else if (event.type === "fridge_open") {
      const w = findWorker(event.aisle, null);
      const wn = w ? w.name : "Any worker";
      const msg = "URGENT. " + wn + ". Fridge door open, " + event.side + " side, Aisle " + event.aisle + ". Close immediately. Product temperature at risk.";
      agentSpeak(msg, true);
      if (w) setWorkers(prev => prev.map(x => x.id === w.id ? { ...x, status: "busy" } : x));
      setTickets(prev => [...prev, { ticketId, type: "fridge", priority, status: "assigned", assignee: wn, location: "Aisle " + event.aisle + ", " + event.side + " fridge", sla, createdAt: new Date() }]);
      acts.push({
        action: "radio_announce", message: "CRITICAL: " + msg, timestamp: now, urgent: true,
        modelTrace: 'detect: fridge_open (conf=' + event.confidence + ')\n  -> priority: CRITICAL (sla=2min)\n  -> assign_worker(task="fridge_close", aisle=' + event.aisle + ')\n  -> create_ticket(type="fridge", priority="CRITICAL")'
      });
    } else if (event.type === "misalignment") {
      const item = inventory[event.product_sku];
      const aisle = item ? item.aisle : event.aisle;
      const w = findWorker(aisle, null);
      const wn = w ? w.name : "Any worker";
      const loc = item ? "Aisle " + item.aisle + ", Row " + item.row_num : event.camera;
      const msg = wn + ". " + loc + ". " + (item ? item.name + " products are" : "Products") + " misaligned. Please face and straighten.";
      agentSpeak(msg);
      if (w) setWorkers(prev => prev.map(x => x.id === w.id ? { ...x, status: "busy" } : x));
      setTickets(prev => [...prev, { ticketId, type: "alignment", priority, status: "assigned", assignee: wn, product: item ? item.name : null, location: loc, sla, createdAt: new Date() }]);
      acts.push({
        action: "radio_announce", message: "Radio: " + msg, timestamp: now,
        modelTrace: 'detect: misalignment (conf=' + event.confidence + ')\n  -> assign_worker(task="fix_alignment", aisle=' + aisle + ', priority="LOW")\n  -> create_ticket(type="alignment", sla=30min)'
      });
    } else if (event.type === "hygiene") {
      const w = findWorker(null, "Cleaning");
      const wn = w ? w.name : "Any worker";
      const msg = wn + ". Hygiene issue detected. Aisle " + event.aisle + ", Row " + event.row + ". Stain or residue on shelf. Please clean immediately.";
      agentSpeak(msg);
      if (w) setWorkers(prev => prev.map(x => x.id === w.id ? { ...x, status: "busy" } : x));
      setTickets(prev => [...prev, { ticketId, type: "cleaning", priority, status: "assigned", assignee: wn, location: "Aisle " + event.aisle + ", Row " + event.row, sla, createdAt: new Date() }]);
      acts.push({
        action: "radio_announce", message: "Radio: " + msg, timestamp: now,
        modelTrace: 'detect: hygiene_issue (conf=' + event.confidence + ')\n  -> assign_worker(task="clean_shelf", role="Cleaning", priority="MEDIUM")\n  -> create_ticket(type="cleaning", sla=10min)'
      });
    }

    const lat = (performance.now() - t0).toFixed(1);
    acts.forEach(a => { a.latencyMs = lat; a.ticketId = ticketId; });
    setActionLog(prev => [...prev, ...acts]);
  }, [inventory, workers, findWorker, agentSpeak]);

  useEffect(() => {
    if (!isRunning || eventIdx >= VISION_EVENTS.length) {
      if (eventIdx >= VISION_EVENTS.length) setIsRunning(false);
      return;
    }
    const t = setTimeout(() => {
      processEvent(VISION_EVENTS[eventIdx]);
      setEventIdx(p => p + 1);
    }, 3500);
    return () => clearTimeout(t);
  }, [isRunning, eventIdx, processEvent]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [actionLog, visionLog]);

  const approveOrder = (ticketId) => {
    const ticket = tickets.find(t => t.ticketId === ticketId);
    if (!ticket) return;
    setTickets(prev => prev.map(t => t.ticketId === ticketId ? { ...t, status: "ordered", approved: true, assignee: "Auto-Order" } : t));
    setVendorOrders(prev => prev.map(o => o.ticketId === ticketId ? { ...o, status: "approved" } : o));
    agentSpeak("Manager approved. Now calling " + ticket.vendor + " to order " + ticket.orderQty + " units of " + ticket.product + ".");
    setTimeout(() => {
      setCallInProgress(ticketId);
      setVendorOrders(prev => prev.map(o => o.ticketId === ticketId ? { ...o, status: "calling" } : o));
      const script = "Hello, this is an automated order from Store 142. We need " + ticket.orderQty + " units of " + ticket.product + ". SKU " + ticket.sku + ". Please confirm and arrange priority delivery. Thank you.";
      agentSpeak(script);
      setActionLog(prev => [...prev, { action: "vendor_call", ticketId, message: "Calling " + ticket.vendor + " at " + ticket.vendorPhone + ": " + script, timestamp: new Date().toLocaleTimeString() }]);
      setTimeout(() => {
        setCallInProgress(null);
        setVendorOrders(prev => prev.map(o => o.ticketId === ticketId ? { ...o, status: "confirmed" } : o));
        setTickets(prev => prev.map(t => t.ticketId === ticketId ? { ...t, status: "ordered" } : t));
        agentSpeak("Vendor call complete. " + ticket.vendor + " confirmed order of " + ticket.orderQty + " units of " + ticket.product + ". Estimated delivery within 24 hours.");
        setActionLog(prev => [...prev, { action: "vendor_confirmed", ticketId, message: ticket.vendor + " confirmed: " + ticket.orderQty + "x " + ticket.product + ". ETA 24hrs.", timestamp: new Date().toLocaleTimeString() }]);
      }, 8000);
    }, 1500);
  };

  const denyOrder = (ticketId) => {
    setTickets(prev => prev.map(t => t.ticketId === ticketId ? { ...t, status: "resolved", approved: false } : t));
    setVendorOrders(prev => prev.map(o => o.ticketId === ticketId ? { ...o, status: "denied" } : o));
    agentSpeak("Manager denied the vendor order for ticket " + ticketId + ". Ticket closed.");
  };

  const resolveTicket = (ticketId) => {
    const ticket = tickets.find(t => t.ticketId === ticketId);
    setTickets(prev => prev.map(t => t.ticketId === ticketId ? { ...t, status: "resolved", resolvedAt: new Date() } : t));
    if (ticket) setWorkers(prev => prev.map(w => w.name === ticket.assignee ? { ...w, status: "available" } : w));
    agentSpeak("Confirmed. Ticket " + ticketId + " resolved. Thank you " + (ticket ? ticket.assignee : "") + ".");
  };

  const resetDemo = () => {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    tktSeq = 0;
    setWorkers(JSON.parse(JSON.stringify(INIT_WORKERS)));
    setTickets([]); setActionLog([]); setVisionLog([]); setVendorOrders([]);
    setEventIdx(0); setIsRunning(false); setSelectedTicket(null); setCallInProgress(null); setSpeakingNow(null);
  };

  const openTickets = tickets.filter(t => t.status !== "resolved");
  const pendingApprovals = tickets.filter(t => t.type === "vendor_order" && !t.approved && t.status === "open");

  return (
    <div style={{ background: "#030712", color: "#e5e7eb", minHeight: "100vh", fontFamily: "'Inter', -apple-system, system-ui, sans-serif" }}>
      {speakingNow && (
        <div style={{ background: "linear-gradient(90deg, #4f46e5, #7c3aed)", padding: "10px 24px", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
            {[0,1,2,3,4].map(i => <div key={i} style={{ width: 3, background: "#fff", borderRadius: 2, animation: "bar " + (0.4 + i * 0.1) + "s ease-in-out infinite alternate", height: 12 }} />)}
          </div>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>Agent Speaking:</span>
          <span style={{ fontSize: 12, color: "#e0e7ff", flex: 1 }}>{speakingNow.length > 120 ? speakingNow.slice(0, 120) + "..." : speakingNow}</span>
        </div>
      )}

      {callInProgress && (
        <div style={{ background: "linear-gradient(90deg, #be185d, #9333ea)", padding: "10px 24px", display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 20, animation: "ring 1s infinite" }}>{"\\ud83d\\udcde"}</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>Vendor Call Active</span>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#22c55e", animation: "pulse 1s infinite" }} />
        </div>
      )}

      {pendingApprovals.length > 0 && !callInProgress && (
        <div style={{ background: "linear-gradient(90deg, #92400e, #b45309)", padding: "10px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>{pendingApprovals.length} vendor order{pendingApprovals.length > 1 ? "s" : ""} awaiting approval</span>
          <button onClick={() => setTab("orders")} style={{ background: "#fff", color: "#92400e", border: "none", borderRadius: 6, padding: "5px 14px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>Review Now</button>
        </div>
      )}

      <div style={{ background: "linear-gradient(135deg, #0f172a, #1e1b4b)", borderBottom: "1px solid #1f2937", padding: "14px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: isRunning ? "#22c55e" : "#6b7280", boxShadow: isRunning ? "0 0 8px #22c55e" : "none" }} />
          <div>
            <div style={{ fontSize: 17, fontWeight: 700, color: "#f9fafb" }}>Store #142 — Manager Command Center</div>
            <div style={{ fontSize: 11, color: "#9ca3af" }}>Gemma 3n Vision + FunctionGemma Agent + MySQL + On-Prem</div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button onClick={() => { setTtsEnabled(!ttsEnabled); if (ttsEnabled && window.speechSynthesis) window.speechSynthesis.cancel(); }}
            style={{ background: ttsEnabled ? "#4f46e522" : "#1f2937", color: ttsEnabled ? "#818cf8" : "#6b7280", border: "1px solid " + (ttsEnabled ? "#4f46e5" : "#374151"), borderRadius: 8, padding: "7px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
            {ttsEnabled ? "Voice ON" : "Voice OFF"}
          </button>
          <button onClick={() => setIsRunning(true)} disabled={isRunning || eventIdx >= VISION_EVENTS.length}
            style={{ background: isRunning ? "#374151" : "#22c55e", color: "#fff", border: "none", borderRadius: 8, padding: "7px 18px", fontSize: 13, fontWeight: 600, cursor: isRunning ? "default" : "pointer", opacity: eventIdx >= VISION_EVENTS.length ? 0.4 : 1 }}>
            {isRunning ? "Processing..." : eventIdx >= VISION_EVENTS.length ? "Done" : "Start Feed"}
          </button>
          <button onClick={() => { if (!isRunning && eventIdx < VISION_EVENTS.length) { processEvent(VISION_EVENTS[eventIdx]); setEventIdx(p => p + 1); }}}
            disabled={isRunning || eventIdx >= VISION_EVENTS.length}
            style={{ background: "#1f2937", color: "#e5e7eb", border: "1px solid #374151", borderRadius: 8, padding: "7px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Step</button>
          <button onClick={resetDemo} style={{ background: "#1f2937", color: "#e5e7eb", border: "1px solid #374151", borderRadius: 8, padding: "7px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Reset</button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 0, borderBottom: "1px solid #1f2937", background: "#0a0f1a", overflowX: "auto" }}>
        {[
          { key: "dashboard", label: "Dashboard", badge: null },
          { key: "orders", label: "Vendor Orders", badge: pendingApprovals.length || null },
          { key: "tickets", label: "Tickets", badge: openTickets.length || null },
          { key: "agent_log", label: "Agent Trace", badge: null },
          { key: "architecture", label: "Architecture", badge: null },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{ padding: "10px 22px", background: "none", border: "none", borderBottom: tab === t.key ? "2px solid #818cf8" : "2px solid transparent", color: tab === t.key ? "#818cf8" : "#6b7280", fontSize: 13, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" }}>
            {t.label}
            {t.badge ? <span style={{ background: t.key === "orders" ? "#f97316" : "#ef4444", color: "#fff", borderRadius: 10, padding: "1px 6px", fontSize: 10, marginLeft: 6 }}>{t.badge}</span> : null}
          </button>
        ))}
      </div>

      <div style={{ padding: 20, maxWidth: 1200, margin: "0 auto" }}>

        {tab === "dashboard" && (
          <div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 20 }}>
              {[
                { l: "Events", v: visionLog.length, c: "#818cf8" },
                { l: "Open Tickets", v: openTickets.length, c: openTickets.length > 3 ? "#ef4444" : "#f97316" },
                { l: "Resolved", v: tickets.filter(t => t.status === "resolved").length, c: "#22c55e" },
                { l: "Pending Orders", v: pendingApprovals.length, c: pendingApprovals.length > 0 ? "#f97316" : "#6b7280" },
                { l: "Active Calls", v: callInProgress ? 1 : 0, c: callInProgress ? "#ec4899" : "#6b7280" },
              ].map((s, i) => (
                <Card key={i}>
                  <div style={{ fontSize: 10, color: "#6b7280", marginBottom: 2 }}>{s.l}</div>
                  <div style={{ fontSize: 26, fontWeight: 800, color: s.c }}>{s.v}</div>
                </Card>
              ))}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16 }}>
              <Card>
                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Live Vision Feed (Gemma 3n)</div>
                <div ref={logRef} style={{ maxHeight: 360, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
                  {visionLog.length === 0 && <div style={{ color: "#4b5563", fontSize: 13, padding: 20, textAlign: "center" }}>Waiting for camera feed...</div>}
                  {visionLog.map((v, i) => (
                    <div key={i} style={{ background: "#0a0f1a", borderRadius: 8, padding: 12, borderLeft: "3px solid " + PRIO_CLR[PRIO[v.type]] }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <span>{ICONS[v.type]}</span>
                          <Badge color={PRIO_CLR[PRIO[v.type]]}>{PRIO[v.type]}</Badge>
                          <span style={{ fontSize: 11, color: "#9ca3af" }}>{v.camera}</span>
                        </div>
                        <span style={{ fontSize: 10, color: "#6b7280" }}>{v.timestamp}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "#d1d5db", lineHeight: 1.4 }}>{v.description}</div>
                      <div style={{ fontSize: 10, color: "#6b7280", marginTop: 3 }}>Confidence: {(v.confidence * 100).toFixed(0)}%</div>
                    </div>
                  ))}
                </div>
              </Card>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <Card>
                  <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>Workers</div>
                  {workers.map(w => (
                    <div key={w.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderBottom: "1px solid #1f2937" }}>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600 }}>{w.name}</div>
                        <div style={{ fontSize: 10, color: "#6b7280" }}>{w.zone}</div>
                      </div>
                      <Badge color={w.status === "available" ? "#22c55e" : "#f97316"}>{w.status}</Badge>
                    </div>
                  ))}
                </Card>
                <Card>
                  <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>Low Stock</div>
                  {Object.values(inventory).filter(v => v.shelf_qty <= 2).map(v => (
                    <div key={v.sku} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid #1f2937", fontSize: 11 }}>
                      <span>{v.name}</span>
                      <span>
                        <span style={{ color: v.shelf_qty === 0 ? "#ef4444" : "#eab308" }}>S:{v.shelf_qty}</span>{" "}
                        <span style={{ color: v.backroom_qty > 0 ? "#22c55e" : "#ef4444" }}>B:{v.backroom_qty}</span>
                      </span>
                    </div>
                  ))}
                </Card>
              </div>
            </div>
          </div>
        )}

        {tab === "orders" && (
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>Vendor Orders — Manager Approval</div>
            {vendorOrders.length === 0 && <Card><div style={{ textAlign: "center", padding: 32, color: "#4b5563" }}>No vendor orders yet.</div></Card>}
            {vendorOrders.map(o => {
              const isPending = o.status === "pending_approval";
              const isCalling = o.status === "calling";
              const borderColor = isPending ? "#f97316" : isCalling ? "#ec4899" : o.status === "confirmed" ? "#22c55e" : "#8b5cf6";
              const badgeLabel = isPending ? "AWAITING APPROVAL" : isCalling ? "CALLING VENDOR" : o.status === "confirmed" ? "CONFIRMED" : o.status === "denied" ? "DENIED" : o.status.toUpperCase();
              const badgeColor = isPending ? "#f97316" : isCalling ? "#ec4899" : o.status === "denied" ? "#ef4444" : "#22c55e";
              return (
                <Card key={o.ticketId} style={{ marginBottom: 12, borderLeft: "3px solid " + borderColor }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#818cf8", fontSize: 13 }}>{o.ticketId}</span>
                      <Badge color={badgeColor}>{badgeLabel}</Badge>
                    </div>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, fontSize: 12, color: "#9ca3af", marginBottom: 12 }}>
                    <div>Product: <span style={{ color: "#e5e7eb", fontWeight: 600 }}>{o.product}</span></div>
                    <div>Quantity: <span style={{ color: "#e5e7eb", fontWeight: 600 }}>{o.qty} units</span></div>
                    <div>Cost: <span style={{ color: "#e5e7eb", fontWeight: 600 }}>${o.cost}</span></div>
                    <div>Vendor: <span style={{ color: "#e5e7eb", fontWeight: 600 }}>{o.vendor}</span></div>
                    <div>Phone: <span style={{ color: "#e5e7eb", fontWeight: 600 }}>{o.vendorPhone}</span></div>
                    <div>SKU: <span style={{ color: "#e5e7eb", fontFamily: "monospace" }}>{o.sku}</span></div>
                  </div>
                  {isPending && (
                    <div style={{ display: "flex", gap: 10, paddingTop: 10, borderTop: "1px solid #1f2937" }}>
                      <button onClick={() => approveOrder(o.ticketId)}
                        style={{ background: "#22c55e", color: "#fff", border: "none", borderRadius: 8, padding: "10px 28px", fontSize: 13, fontWeight: 700, cursor: "pointer", flex: 1 }}>
                        Approve and Call Vendor
                      </button>
                      <button onClick={() => denyOrder(o.ticketId)}
                        style={{ background: "#1f2937", color: "#ef4444", border: "1px solid #374151", borderRadius: 8, padding: "10px 28px", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                        Deny
                      </button>
                    </div>
                  )}
                  {isCalling && (
                    <div style={{ paddingTop: 10, borderTop: "1px solid #1f2937", display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "#ec4899" }}>Calling {o.vendor}...</div>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#22c55e", animation: "pulse 1s infinite" }} />
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}

        {tab === "tickets" && (
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 12 }}>Active Tickets ({openTickets.length})</div>
            {tickets.length === 0 && <Card><div style={{ textAlign: "center", padding: 32, color: "#4b5563" }}>No tickets yet.</div></Card>}
            {tickets.map(t => (
              <Card key={t.ticketId} onClick={() => setSelectedTicket(t.ticketId === selectedTicket ? null : t.ticketId)}
                style={{ marginBottom: 8, cursor: "pointer", borderLeft: "3px solid " + PRIO_CLR[t.priority], opacity: t.status === "resolved" ? 0.5 : 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#818cf8", fontSize: 12 }}>{t.ticketId}</span>
                    <Badge color={PRIO_CLR[t.priority]}>{t.priority}</Badge>
                    <Badge color={STAT_CLR[t.status] || "#6b7280"}>{t.status.toUpperCase()}</Badge>
                    <span style={{ fontSize: 12, color: "#d1d5db" }}>{t.type} — {t.location}</span>
                  </div>
                  <span style={{ fontSize: 11, color: "#6b7280" }}>{t.assignee}</span>
                </div>
                {selectedTicket === t.ticketId && (
                  <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid #1f2937" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 11, color: "#9ca3af", marginBottom: 10 }}>
                      {t.product && <div>Product: <span style={{ color: "#e5e7eb" }}>{t.product}</span></div>}
                      <div>SLA: <span style={{ color: "#e5e7eb" }}>{t.sla} min</span></div>
                      {t.vendor && <div>Vendor: <span style={{ color: "#e5e7eb" }}>{t.vendor}</span></div>}
                      <div>Created: <span style={{ color: "#e5e7eb" }}>{t.createdAt ? t.createdAt.toLocaleTimeString() : ""}</span></div>
                    </div>
                    {t.status !== "resolved" && t.type !== "vendor_order" && (
                      <button onClick={e => { e.stopPropagation(); resolveTicket(t.ticketId); }}
                        style={{ background: "#22c55e", color: "#fff", border: "none", borderRadius: 6, padding: "6px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                        Worker says "Done"
                      </button>
                    )}
                    {t.status === "resolved" && t.resolvedAt && <div style={{ fontSize: 12, color: "#22c55e" }}>Resolved at {t.resolvedAt.toLocaleTimeString()}</div>}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}

        {tab === "agent_log" && (
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>FunctionGemma Agent Trace</div>
            <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 14 }}>Every decision made by the model — no hardcoded routing. Multi-step tool calling loop.</div>
            <Card style={{ maxHeight: 550, overflowY: "auto" }}>
              {actionLog.length === 0 && <div style={{ color: "#4b5563", textAlign: "center", padding: 32 }}>Agent idle. Start camera feed to see model reasoning...</div>}
              {actionLog.map((a, i) => (
                <div key={i} style={{ padding: "10px 0", borderBottom: "1px solid #1f293730" }}>
                  <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 6 }}>
                    <span style={{ fontSize: 10, color: "#6b7280", fontFamily: "monospace" }}>{a.timestamp}</span>
                    {a.latencyMs && <Badge color="#818cf8">{a.latencyMs}ms</Badge>}
                    <Badge color={
                      a.action === "vendor_call" || a.action === "vendor_confirmed" ? "#ec4899" :
                      a.action === "manager_approval_needed" ? "#f97316" :
                      a.urgent ? "#ef4444" : "#3b82f6"
                    }>
                      {(a.action || "").replace(/_/g, " ").toUpperCase()}
                    </Badge>
                    {a.ticketId && <span style={{ fontSize: 10, color: "#818cf8", fontFamily: "monospace" }}>{a.ticketId}</span>}
                  </div>
                  {a.modelTrace && (
                    <div style={{ background: "#0d1117", borderRadius: 6, padding: 10, marginBottom: 6, borderLeft: "2px solid #818cf8" }}>
                      <div style={{ fontSize: 10, color: "#818cf8", marginBottom: 4, fontWeight: 700 }}>FunctionGemma tool_call chain</div>
                      <pre style={{ margin: 0, fontSize: 11, color: "#c9d1d9", whiteSpace: "pre-wrap", fontFamily: "monospace" }}>{a.modelTrace}</pre>
                    </div>
                  )}
                  <div style={{ color: "#d1d5db", lineHeight: 1.5, fontSize: 12, paddingLeft: 2 }}>{a.message}</div>
                </div>
              ))}
            </Card>
          </div>
        )}

        {tab === "architecture" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>System Architecture</div>
              <div style={{ fontFamily: "monospace", fontSize: 11, color: "#9ca3af", lineHeight: 2, overflowX: "auto" }}>
                <div style={{ color: "#818cf8", fontWeight: 700 }}>{"┌──────────────── ON-PREMISES ────────────────┐"}</div>
                <div>{"│"} <span style={{ color: "#22c55e" }}>Cameras (10-30)</span>{"                             │"}</div>
                <div>{"│     │ RTSP (never leaves building)           │"}</div>
                <div>{"│     v                                       │"}</div>
                <div>{"│"} <span style={{ color: "#eab308" }}>Gemma 3n (Local GPU)</span>{"                      │"}</div>
                <div>{"│     │ structured text output                 │"}</div>
                <div>{"│     v                                       │"}</div>
                <div>{"│"} <span style={{ color: "#f97316" }}>FunctionGemma (LoRA fine-tuned)</span>{"            │"}</div>
                <div>{"│     │ Model decides tool calls               │"}</div>
                <div>{"│     │ Multi-step loop until <done>           │"}</div>
                <div>{"│     ├→ query_inventory() → "}<span style={{ color: "#3b82f6" }}>MySQL</span>{"           │"}</div>
                <div>{"│     ├→ assign_worker()   → "}<span style={{ color: "#3b82f6" }}>Radio TTS</span>{"       │"}</div>
                <div>{"│     ├→ request_vendor_order() → "}<span style={{ color: "#ec4899" }}>Voice call</span>{"  │"}</div>
                <div>{"│     ├→ escalate_to_manager() → "}<span style={{ color: "#f97316" }}>Dashboard</span>{"   │"}</div>
                <div>{"│     └→ create_ticket()   → "}<span style={{ color: "#3b82f6" }}>MySQL</span>{"           │"}</div>
                <div>{"│     v                                       │"}</div>
                <div>{"│"} <span style={{ color: "#8b5cf6" }}>Voice I/O (edge-tts + Whisper)</span>{"             │"}</div>
                <div>{"│     Worker: \"Done\" → close_ticket()          │"}</div>
                <div style={{ color: "#818cf8", fontWeight: 700 }}>{"└──── ZERO CLOUD · ZERO COST/INFERENCE ────────┘"}</div>
              </div>
            </Card>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                { t: "Latency < 50ms", d: "Fridge alerts can't wait for cloud round-trips." },
                { t: "GDPR/CCPA Safe", d: "24/7 cameras capture customers. Frames never leave." },
                { t: "$0 Per Inference", d: "30 cameras continuous = thousands/mo on cloud." },
                { t: "Offline Resilient", d: "Internet down? System keeps running. Syncs later." },
              ].map((r, i) => (
                <Card key={i}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "#e5e7eb", marginBottom: 4 }}>{r.t}</div>
                  <div style={{ fontSize: 11, color: "#9ca3af", lineHeight: 1.4 }}>{r.d}</div>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>

      <style>{"\
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }\
        @keyframes ring { 0%{transform:rotate(0)} 25%{transform:rotate(15deg)} 50%{transform:rotate(-15deg)} 75%{transform:rotate(10deg)} 100%{transform:rotate(0)} }\
        @keyframes bar { from{height:4px} to{height:18px} }\
      "}</style>
    </div>
  );
}
