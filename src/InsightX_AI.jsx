import { useState, useRef, useEffect } from "react";
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis } from "recharts";

// ── API CONFIG — change this if your backend runs on a different port ─────────
const API_BASE = "http://localhost:8000";

// ── ANALYTICS DATA (pre-computed from 250,000 UPI transactions 2024) ──────────
const DATA = {
  total_transactions: 250000,
  total_volume: 327939009,
  avg_amount: 1311.76,
  fraud_count: 480,
  fraud_rate: 0.192,
  success_rate: 95.05,
  categories: { Grocery: 49966, Food: 37464, Shopping: 29872, Fuel: 25063, Other: 24828, Utilities: 22338, Transport: 20105, Entertainment: 20103, Healthcare: 12663, Education: 7598 },
  states: { Maharashtra: 37427, "Uttar Pradesh": 30125, Karnataka: 29756, "Tamil Nadu": 25367, Delhi: 24870, Telangana: 22435, Gujarat: 20061, "Andhra Pradesh": 20006, Rajasthan: 19981, "West Bengal": 19972 },
  devices: { Android: 187777, iOS: 49613, Web: 12610 },
  networks: { "4G": 149813, "5G": 62582, WiFi: 25134, "3G": 12471 },
  banks: { SBI: 62693, HDFC: 37485, ICICI: 29769, IndusInd: 25173, Axis: 25042, PNB: 24946, "Yes Bank": 24860, Kotak: 20032 },
  tx_types: { P2P: 112445, P2M: 87660, "Bill Payment": 37368, Recharge: 12527 },
  age_groups: { "26-35": 87432, "36-45": 62873, "18-25": 62345, "46-55": 24841, "56+": 12509 },
  hourly: {
    sum: { 0: 4532884, 1: 2914350, 2: 2173750, 3: 1678669, 4: 1670700, 5: 2134122, 6: 4617034, 7: 7482766, 8: 10979614, 9: 13809021, 10: 18337313, 11: 21193161, 12: 23406280, 13: 19847819, 14: 14848621, 15: 16658144, 16: 17921125, 17: 24514186, 18: 26297174, 19: 28223522, 20: 23822014, 21: 20995491, 22: 12050824, 23: 7830425 },
    count: { 0: 3388, 1: 2244, 2: 1685, 3: 1314, 4: 1247, 5: 1742, 6: 3501, 7: 5630, 8: 8349, 9: 10450, 10: 13904, 11: 16328, 12: 17516, 13: 15038, 14: 11472, 15: 12624, 16: 13992, 17: 18340, 18: 20064, 19: 21232, 20: 18506, 21: 16253, 22: 9364, 23: 5817 }
  },
  daily: {
    count: { Monday: 36495, Tuesday: 35540, Wednesday: 35700, Thursday: 35432, Friday: 35496, Saturday: 35334, Sunday: 36003 },
    sum: { Monday: 47882908, Tuesday: 46846390, Wednesday: 46815663, Thursday: 46620985, Friday: 46332583, Saturday: 45867936, Sunday: 47572544 }
  },
  cat_fraud: { Education: 0.211, Entertainment: 0.199, Food: 0.195, Fuel: 0.192, Grocery: 0.188, Healthcare: 0.166, Other: 0.201, Shopping: 0.208, Transport: 0.214, Utilities: 0.148 },
  state_vol: { "Andhra Pradesh": 25952619, Delhi: 32689865, Gujarat: 25988190, Karnataka: 38451158, Maharashtra: 49043948, Rajasthan: 26730470, "Tamil Nadu": 33343518, Telangana: 29750930, "Uttar Pradesh": 40035717, "West Bengal": 25952594 },
  state_fraud: { "Andhra Pradesh": 0.175, Delhi: 0.201, Gujarat: 0.214, Karnataka: 0.232, Maharashtra: 0.19, Rajasthan: 0.23, "Tamil Nadu": 0.158, Telangana: 0.174, "Uttar Pradesh": 0.173, "West Bengal": 0.175 },
  device_avg: { Android: 1313.98, iOS: 1306.10, Web: 1300.81 },
  device_median: { Android: 629, iOS: 632, Web: 615 },
  device_max: { Android: 42099, iOS: 30351, Web: 27541 },
  device_min: { Android: 10, iOS: 10, Web: 13 },
  device_std: { Android: 1852.41, iOS: 1831.36, Web: 1848.74 },
  device_total_vol: { Android: 246736086, iOS: 64799708, Web: 16403215 },
  device_p90: { Android: 3251, iOS: 3199, Web: 3185 },
  device_p95: { Android: 4700, iOS: 4634, Web: 4657 },
  device_fraud: { Android: 0.194, iOS: 0.181, Web: 0.206 },
  device_fraud_count: { Android: 364, iOS: 90, Web: 26 },
  device_fail_rate: { Android: 4.94, iOS: 4.93, Web: 5.15 },
  device_success_rate: { Android: 95.06, iOS: 95.07, Web: 94.85 },
  device_cat_avg: {
    Education: { Android: 5093.24, iOS: 5116.23, Web: 5026.92 },
    Entertainment: { Android: 413.77, iOS: 413.07, Web: 407.67 },
    Food: { Android: 528.78, iOS: 542.16, Web: 534.71 },
    Fuel: { Android: 1555.57, iOS: 1554.83, Web: 1554.80 },
    Grocery: { Android: 1169.67, iOS: 1161.03, Web: 1137.12 },
    Healthcare: { Android: 545.10, iOS: 542.35, Web: 511.03 },
    Other: { Android: 847.00, iOS: 847.86, Web: 878.38 },
    Shopping: { Android: 2592.11, iOS: 2524.61, Web: 2482.87 },
    Transport: { Android: 308.79, iOS: 303.56, Web: 314.01 },
    Utilities: { Android: 2355.59, iOS: 2384.35, Web: 2353.66 },
  },
  network_fraud: { "3G": 0.192, "4G": 0.188, "5G": 0.184, WiFi: 0.235 },
  cat_avg: { Education: 5094.02, Entertainment: 413.33, Food: 531.69, Fuel: 1555.38, Grocery: 1166.35, Healthcare: 542.85, Other: 848.78, Shopping: 2573.09, Transport: 308.0, Utilities: 2361.11 },
  cat_vol: { Education: 38704346, Entertainment: 8309080, Food: 19919402, Fuel: 38982575, Grocery: 58277893, Healthcare: 6874159, Other: 21073449, Shopping: 76863207, Transport: 6192416, Utilities: 52742482 },
  bank_fraud: { Axis: 0.196, HDFC: 0.165, ICICI: 0.222, IndusInd: 0.207, Kotak: 0.25, PNB: 0.208, SBI: 0.174, "Yes Bank": 0.161 },
  age_fraud: { "18-25": 0.229, "26-35": 0.186, "36-45": 0.184, "46-55": 0.125, "56+": 0.216 },
  age_avg: { "18-25": 1194.55, "26-35": 1326.29, "36-45": 1424.04, "46-55": 1333.13, "56+": 1187.57 },
  type_fraud: { "Bill Payment": 0.206, P2M: 0.191, P2P: 0.183, Recharge: 0.239 },
  type_avg: { "Bill Payment": 1308.49, P2M: 1320.07, P2P: 1308.68, Recharge: 1290.9 },
  cat_fail: { Education: 5.25, Entertainment: 4.92, Food: 5.01, Fuel: 4.8, Grocery: 5.01, Healthcare: 4.83, Other: 4.95, Shopping: 5.09, Transport: 4.76, Utilities: 4.86 },
  peak_hour: 19,
  top_state: "Maharashtra",
  top_cat: "Grocery",
  max_amount: 42099,
  min_amount: 10,
  median_amount: 629,
  amount_buckets: { "< ₹100": 13099, "₹100–500": 93363, "₹500–1K": 51135, "₹1K–5K": 81444, "₹5K–10K": 9154, "> ₹10K": 1805 },
  top10_amounts: [
    { amount: 42099, category: "Education", type: "P2P", state: "Telangana", device: "Android", network: "4G", status: "FAILED", fraud: 0, hour: 1, day: "Sunday" },
    { amount: 41210, category: "Education", type: "Bill Payment", state: "Maharashtra", device: "Android", network: "4G", status: "SUCCESS", fraud: 0, hour: 14, day: "Saturday" },
    { amount: 37263, category: "Education", type: "Recharge", state: "Rajasthan", device: "Android", network: "WiFi", status: "SUCCESS", fraud: 0, hour: 22, day: "Tuesday" },
    { amount: 34304, category: "Education", type: "P2P", state: "Andhra Pradesh", device: "Android", network: "5G", status: "SUCCESS", fraud: 0, hour: 17, day: "Friday" },
    { amount: 33061, category: "Education", type: "P2P", state: "Rajasthan", device: "Android", network: "WiFi", status: "SUCCESS", fraud: 0, hour: 23, day: "Monday" },
    { amount: 32741, category: "Education", type: "P2P", state: "West Bengal", device: "Android", network: "WiFi", status: "SUCCESS", fraud: 0, hour: 17, day: "Friday" },
    { amount: 30584, category: "Education", type: "P2P", state: "Andhra Pradesh", device: "Android", network: "5G", status: "SUCCESS", fraud: 0, hour: 20, day: "Wednesday" },
    { amount: 30351, category: "Utilities", type: "P2P", state: "West Bengal", device: "iOS", network: "WiFi", status: "SUCCESS", fraud: 0, hour: 23, day: "Wednesday" },
    { amount: 30112, category: "Education", type: "P2M", state: "Telangana", device: "Android", network: "5G", status: "SUCCESS", fraud: 0, hour: 21, day: "Monday" },
    { amount: 29601, category: "Education", type: "P2M", state: "Uttar Pradesh", device: "Android", network: "3G", status: "SUCCESS", fraud: 0, hour: 7, day: "Tuesday" },
  ],
  high_value_count: 1805,
  fraud_avg_amount: 1499.23,
};

// ── THEME ─────────────────────────────────────────────────────────────────────
const THEME = {
  bg: "#f8fafc", surface: "#ffffff", surfaceHover: "#f1f5f9",
  border: "#e2e8f0", borderSoft: "#cbd5e1",
  textPrimary: "#1e293b", textSecondary: "#64748b", textLight: "#94a3b8",
  blue: "#2563eb", blueLight: "#3b82f6", blueSoft: "#dbeafe", bluePale: "#eff6ff",
  accent: "#0ea5e9", danger: "#ef4444", success: "#10b981", warning: "#f59e0b",
  chartGrid: "#f1f5f9", chartText: "#64748b",
  gradient: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)"
};

const fmt    = (n) => n >= 1e7 ? `₹${(n/1e7).toFixed(1)}Cr` : n >= 1e5 ? `₹${(n/1e5).toFixed(1)}L` : n >= 1000 ? `₹${(n/1000).toFixed(1)}K` : `₹${n}`;
const fmtNum = (n) => n >= 1e6 ? `${(n/1e6).toFixed(1)}M` : n >= 1e3 ? `${(n/1e3).toFixed(1)}K` : n;
const COLORS = ["#2563eb","#3b82f6","#0ea5e9","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#6366f1","#ec4899"];

const hourlyChartData  = Array.from({length:24},(_,h)=>({hour:`${h}:00`,volume:Math.round(DATA.hourly.sum[h]/1e6*10)/10,txns:DATA.hourly.count[h]}));
const dailyChartData   = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].map(d=>({day:d.slice(0,3),volume:Math.round(DATA.daily.sum[d]/1e6),txns:DATA.daily.count[d]}));
const catChartData     = Object.entries(DATA.categories).map(([k,v])=>({name:k,txns:v,volume:Math.round((DATA.cat_vol[k]||0)/1e6),avg:DATA.cat_avg[k]||0,fraud:DATA.cat_fraud[k]||0})).sort((a,b)=>b.txns-a.txns);
const stateChartData   = Object.entries(DATA.state_vol).map(([k,v])=>({state:k.replace(" Pradesh","").replace("Tamil Nadu","TN").replace("West Bengal","WB"),vol:Math.round(v/1e6),fraud:DATA.state_fraud[k]||0})).sort((a,b)=>b.vol-a.vol);
const devicePieData    = Object.entries(DATA.devices).map(([k,v])=>({name:k,value:v}));
const networkPieData   = Object.entries(DATA.networks).map(([k,v])=>({name:k,value:v}));
const bankChartData    = Object.entries(DATA.banks).map(([k,v])=>({bank:k,txns:v,fraud:DATA.bank_fraud[k]||0})).sort((a,b)=>b.txns-a.txns);

const CustomTooltip = ({active,payload,label,prefix="",suffix=""}) => {
  if(active && payload && payload.length) return (
    <div style={{background:"#fff",border:`1px solid ${THEME.border}`,boxShadow:"0 4px 12px rgba(0,0,0,0.08)",borderRadius:8,padding:"10px 14px",minWidth:120}}>
      <p style={{color:THEME.textSecondary,fontSize:11,margin:"0 0 6px",fontWeight:600,textTransform:"uppercase",letterSpacing:0.5}}>{label}</p>
      {payload.map((p,i)=><p key={i} style={{color:p.color||THEME.textPrimary,fontSize:13,margin:"2px 0",fontWeight:600,display:"flex",justifyContent:"space-between",gap:12}}><span>{p.name||"Value"}:</span><span>{prefix}{typeof p.value==="number"&&p.value>100?fmtNum(p.value):p.value}{suffix}</span></p>)}
    </div>
  );
  return null;
};

const SAMPLE_QUERIES = [
  "What is the highest individual transaction amount?",
  "Which merchant category has the highest fraud risk?",
  "What are peak transaction hours?",
  "Compare fraud rates across different states",
  "Which bank has the highest max transaction?",
  "Show me the age group spending patterns",
  "Give me an executive summary of the dataset",
  "Compare average transaction amounts for iOS vs Android",
  "What's the WiFi network fraud anomaly?",
];

// ══════════════════════════════════════════════════════════════════════════════
// DYNAMIC DASHBOARD — rendered from /api/dashboard response after CSV upload
// Matches exact style of old.txt: 4-col grid, kpiCards, chartCards, fullCards
// ══════════════════════════════════════════════════════════════════════════════
function DynamicDashboard({ dash }) {
  const kpiCard = {
    background: THEME.surface, border: `1px solid ${THEME.border}`,
    borderRadius: 16, padding: 20,
    boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)",
    transition: "transform 0.2s, box-shadow 0.2s", gridColumn: "span 1",
  };
  const chartCard = {
    background: THEME.surface, border: `1px solid ${THEME.border}`,
    borderRadius: 16, padding: 20,
    boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)", gridColumn: "span 2",
  };
  const fullCard = {
    background: THEME.surface, border: `1px solid ${THEME.border}`,
    borderRadius: 16, padding: 24,
    boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)", gridColumn: "span 4",
  };
  const sectionTitle = {
    fontSize: 12, fontWeight: 700, color: THEME.textSecondary,
    letterSpacing: 1, marginBottom: 12, textTransform: "uppercase",
  };

  const hover = (e) => { e.currentTarget.style.transform="translateY(-2px)"; e.currentTarget.style.boxShadow="0 10px 15px -3px rgba(0,0,0,0.07)"; };
  const unhover = (e) => { e.currentTarget.style.transform="translateY(0)"; e.currentTarget.style.boxShadow="0 4px 6px -1px rgba(0,0,0,0.05)"; };

  return (
    <div style={{ flex:1, overflowY:"auto", padding:32, display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:24, alignContent:"start", background:THEME.bg }}>

      {/* ── Dataset info banner ─────────────────────────────────────────────── */}
      <div className="dash-card" style={{ ...fullCard, background: THEME.gradient, padding:"18px 24px", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        <div>
          <div style={{ fontSize:18, fontWeight:800, color:"#fff", marginBottom:6 }}>📊 {dash.filename}</div>
          <div style={{ fontSize:13, color:"rgba(255,255,255,0.8)" }}>
            {(dash.rows||0).toLocaleString()} rows &nbsp;·&nbsp; {dash.columns} columns &nbsp;·&nbsp;
            {(dash.num_cols||[]).length} numeric &nbsp;·&nbsp; {(dash.cat_cols||[]).length} categorical
          </div>
        </div>
        <div style={{ fontSize:42, opacity:0.5 }}>⚡</div>
      </div>

      {/* ── KPI Cards ─────────────────────────────────────────────────────────── */}
      {(dash.kpis||[]).map((k, i) => (
        <div key={i} className="dash-card" style={kpiCard} onMouseEnter={hover} onMouseLeave={unhover}>
          <div style={{ fontSize:24, marginBottom:12, opacity:0.85 }}>{k.icon}</div>
          <div style={{ fontSize:22, fontWeight:700, color:THEME.textPrimary, marginBottom:4 }}>{k.val}</div>
          <div style={{ fontSize:12, color:THEME.textSecondary, fontWeight:500 }}>{k.label}</div>
          <div style={{ height:3, width:40, background:k.color, marginTop:12, borderRadius:2 }}/>
        </div>
      ))}

      {/* ── Numeric Distribution Histogram ─────────────────────────────────── */}
      {(dash.num_dist||[]).length > 0 && (
        <div className="dash-card" style={fullCard} onMouseEnter={hover} onMouseLeave={unhover}>
          <p style={sectionTitle}>Distribution — {dash.primary_num_col}</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={dash.num_dist} margin={{ top:10, right:20, bottom:0, left:0 }}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="range" tick={{ fill:THEME.chartText, fontSize:11 }} axisLine={false} tickLine={false}/>
              <YAxis tick={{ fill:THEME.chartText, fontSize:11 }} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip/>} cursor={{ fill:THEME.blueSoft }}/>
              <Bar dataKey="count" radius={[6,6,0,0]}>
                {(dash.num_dist||[]).map((_,i) => <Cell key={i} fill={COLORS[i % COLORS.length]}/>)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Time Series ────────────────────────────────────────────────────── */}
      {(dash.time_series||[]).length > 0 && (
        <div className="dash-card" style={fullCard} onMouseEnter={hover} onMouseLeave={unhover}>
          <p style={sectionTitle}>Monthly Trend — {dash.primary_num_col}</p>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={dash.time_series} margin={{ top:10, right:20, bottom:0, left:0 }}>
              <defs>
                <linearGradient id="tsGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={THEME.blue} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={THEME.blue} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="period" tick={{ fill:THEME.chartText, fontSize:10 }} angle={-20} textAnchor="end" axisLine={false} tickLine={false}/>
              <YAxis tick={{ fill:THEME.chartText, fontSize:11 }} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip/>} cursor={{ fill:THEME.blueSoft }}/>
              <Area type="monotone" dataKey="value" stroke={THEME.blue} fill="url(#tsGrad)" strokeWidth={2.5} dot={false}/>
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Category Bar Charts ─────────────────────────────────────────────── */}
      {(dash.cat_charts||[]).map((cc, ci) => (
        <div key={ci} className="dash-card" style={chartCard} onMouseEnter={hover} onMouseLeave={unhover}>
          <p style={sectionTitle}>{cc.col}{cc.num_col ? ` × ${cc.num_col}` : " (count)"}</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={(cc.data||[]).slice(0,10)} margin={{ top:10, right:10, bottom:30, left:0 }}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="name" tick={{ fill:THEME.chartText, fontSize:10 }} angle={-25} textAnchor="end" axisLine={false} tickLine={false}/>
              <YAxis tick={{ fill:THEME.chartText, fontSize:10 }} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip/>} cursor={{ fill:THEME.blueSoft }}/>
              <Bar dataKey={cc.num_col ? "avg" : "count"} radius={[4,4,0,0]}>
                {(cc.data||[]).slice(0,10).map((_,i) => <Cell key={i} fill={COLORS[i % COLORS.length]}/>)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ))}

      {/* ── Fraud Rate by Category ──────────────────────────────────────────── */}
      {(dash.fraud_by_cat||[]).map((fb, fi) => (
        <div key={fi} className="dash-card" style={chartCard} onMouseEnter={hover} onMouseLeave={unhover}>
          <p style={sectionTitle}>Fraud Rate by {fb.col} (%)</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={(fb.data||[]).slice(0,10)} margin={{ top:10, right:10, bottom:30, left:0 }}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="name" tick={{ fill:THEME.chartText, fontSize:10 }} angle={-25} textAnchor="end" axisLine={false} tickLine={false}/>
              <YAxis tick={{ fill:THEME.chartText, fontSize:10 }} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip suffix="%"/>} cursor={{ fill:THEME.blueSoft }}/>
              <Bar dataKey="rate" fill={THEME.danger} radius={[4,4,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ))}

      {/* ── Correlation Bars ───────────────────────────────────────────────── */}
      {(dash.correlations||[]).length > 0 && (
        <div className="dash-card" style={fullCard} onMouseEnter={hover} onMouseLeave={unhover}>
          <p style={sectionTitle}>Top Correlations Between Numeric Columns</p>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12 }}>
            {(dash.correlations||[]).slice(0,9).map((c, i) => {
              const pct = Math.abs(c.r) * 100;
              const col = c.r > 0.5 ? THEME.success : c.r < -0.5 ? THEME.danger : THEME.warning;
              return (
                <div key={i} style={{ background:THEME.bg, borderRadius:10, padding:"12px 14px", border:`1px solid ${THEME.border}` }}>
                  <div style={{ fontSize:11, color:THEME.textSecondary, marginBottom:8, fontWeight:600 }}>
                    {c.col_a} ↔ {c.col_b}
                  </div>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <div style={{ flex:1, height:6, background:THEME.border, borderRadius:4, overflow:"hidden" }}>
                      <div style={{ height:"100%", width:`${pct}%`, background:col, borderRadius:4 }}/>
                    </div>
                    <span style={{ fontSize:13, fontWeight:700, color:col, minWidth:40, textAlign:"right" }}>
                      {c.r > 0 ? "+" : ""}{c.r}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Auto-Detected Anomalies & Insights ─────────────────────────────── */}
      {(dash.anomalies||[]).length > 0 && (
        <div className="dash-card" style={fullCard} onMouseEnter={hover} onMouseLeave={unhover}>
          <p style={sectionTitle}>🚨 Auto-Detected Anomalies & Insights</p>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:16 }}>
            {(dash.anomalies||[]).map((a, i) => (
              <div key={i} style={{
                background: THEME.bg,
                border: `1px solid ${THEME.border}`,
                borderRadius: 12, padding:"16px",
                borderLeft: `4px solid ${a.color}`,
                transition: "all 0.2s"
              }}>
                <div style={{ fontSize:20, marginBottom:8 }}>{a.icon}</div>
                <div style={{ fontSize:13, fontWeight:700, color:THEME.textPrimary, marginBottom:6 }}>{a.title}</div>
                <div style={{ fontSize:12, color:THEME.textSecondary, lineHeight:1.6 }}>{a.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════════════
// MAIN APP
// ══════════════════════════════════════════════════════════════════════════════
export default function InsightXApp() {
  const [messages, setMessages] = useState([
    { role:"assistant", content:"Welcome to **InsightX AI** — your conversational intelligence layer for 250,000 UPI transactions across India in 2024.\n\nI can answer questions about fraud patterns, transaction volumes, peak hours, state-wise analytics, bank performance, and much more.", chart:null, confidence:null }
  ]);
  const [input, setInput]                 = useState("");
  const [loading, setLoading]             = useState(false);
  const [activeTab, setActiveTab]         = useState("chat");
  const [sessionId, setSessionId]         = useState(null);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [uploadStatus, setUploadStatus]   = useState(null);
  // ── NEW: dashboard state ──────────────────────────────────────────────────
  const [csvLoaded, setCsvLoaded]         = useState(false);   // true after successful upload
  const [dashData, setDashData]           = useState(null);    // data from /api/dashboard
  const [dashLoading, setDashLoading]     = useState(false);

  const chatEndRef   = useRef(null);
  const inputRef     = useRef(null);
  const fileInputRef = useRef(null);

  // ── Check backend health on mount ────────────────────────────────────────
  useEffect(() => {
    fetch(`${API_BASE}/api/health`)
      .then(r => r.json())
      .then(d => { setBackendStatus("ok"); console.log("Backend:", d); })
      .catch(() => setBackendStatus("error"));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior:"smooth" });
  }, [messages, loading]);

  const computeConfidence = (query) => {
    const q = query.toLowerCase();
    const known = ["fraud","volume","transaction","peak","state","category","device","network","bank","age","amount","fail","success"];
    const n = known.filter(t=>q.includes(t)).length;
    if(n>=3) return {score:96,label:"High"};
    if(n>=2) return {score:89,label:"High"};
    if(n>=1) return {score:78,label:"Medium"};
    return {score:65,label:"Medium"};
  };

  // ── Send message → FastAPI backend ───────────────────────────────────────
  const sendMessage = async (text) => {
    const userText = text || input.trim();
    if(!userText) return;
    setInput("");
    setMessages(prev => [...prev, {role:"user",content:userText}]);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ message:userText, session_id:sessionId }),
      });
      if(!res.ok) {
        const err = await res.json().catch(()=>({detail:"Unknown error"}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if(!sessionId) setSessionId(data.session_id);
      const confidence = computeConfidence(userText);
      setMessages(prev => [...prev, { role:"assistant", content:data.reply, chart:data.chart_type, confidence }]);
    } catch(err) {
      setMessages(prev => [...prev, {
        role:"assistant",
        content:`⚠️ **Backend error:** ${err.message}\n\nMake sure the FastAPI server is running:\n\`\`\`\nuvicorn main:app --reload --port 8000\n\`\`\``,
        chart:null, confidence:null,
      }]);
    }
    setLoading(false);
  };

  // ── New chat (clear session) ──────────────────────────────────────────────
  const newChat = async () => {
    if(sessionId) fetch(`${API_BASE}/api/session/${sessionId}`, {method:"DELETE"}).catch(()=>{});
    setSessionId(null);
    setMessages([{role:"assistant",content:"New conversation started. What would you like to know?",chart:null,confidence:null}]);
  };

  // ── CSV Upload → also fetches dashboard stats ────────────────────────────
  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if(!file) return;
    setUploadStatus("uploading");
    const form = new FormData();
    form.append("file", file);
    try {
      // 1. Upload CSV
      const res  = await fetch(`${API_BASE}/api/upload-csv`, {method:"POST", body:form});
      const data = await res.json();
      if(!res.ok) throw new Error(data.detail);
      setUploadStatus("success");

      // 2. Fetch computed dashboard stats
      setDashLoading(true);
      const dr   = await fetch(`${API_BASE}/api/dashboard`);
      const dash = await dr.json();
      setDashLoading(false);

      if(dash.csv_loaded) {
        setDashData(dash);
        setCsvLoaded(true);
      }

      // 3. Auto-switch to dashboard tab
      setActiveTab("dashboard");

      // 4. Post confirmation in chat
      setMessages(prev => [...prev, {
        role:"assistant",
        content:`✅ **New dataset loaded:** \`${data.filename}\`\n- **${data.rows.toLocaleString()} rows** × ${data.columns} columns\n- Columns: ${data.column_names.slice(0,8).join(", ")}${data.column_names.length>8?" …":""}\n\n📊 **Dashboard tab is now active** — click it to explore your data insights!`,
        chart:null, confidence:null,
      }]);
      setTimeout(()=>setUploadStatus(null), 3000);
    } catch(err) {
      setUploadStatus("error");
      setDashLoading(false);
      setTimeout(()=>setUploadStatus(null), 3000);
    }
    e.target.value = ""; // reset so same file can be re-uploaded
  };

  // ── Chart renderer (in-chat, unchanged) ──────────────────────────────────
  const renderChart = (type) => {
    if(!type) return null;
    const cc = {background:THEME.surface,border:`1px solid ${THEME.border}`,borderRadius:12,padding:"16px",marginTop:12};
    const tt = {fontSize:12,color:THEME.textSecondary,margin:"0 0 12px",letterSpacing:0.5,fontWeight:700,textTransform:"uppercase"};
    switch(type) {
      case "amountdist": return (
        <div style={cc}><p style={tt}>Transaction Amount Distribution</p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={Object.entries(DATA.amount_buckets).map(([k,v])=>({range:k,count:v}))} margin={{top:10,right:10,bottom:0,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="range" tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip/>} cursor={{fill:THEME.blueSoft}}/>
              <Bar dataKey="count" radius={[6,6,0,0]}>{Object.keys(DATA.amount_buckets).map((_,i)=><Cell key={i} fill={COLORS[i]}/>)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      case "hourly": return (
        <div style={cc}><p style={tt}>Transaction Volume by Hour (₹M)</p>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={hourlyChartData} margin={{top:10,right:10,bottom:0,left:-10}}>
              <defs><linearGradient id="hg" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={THEME.blue} stopOpacity={0.2}/><stop offset="95%" stopColor={THEME.blue} stopOpacity={0}/></linearGradient></defs>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="hour" tick={{fill:THEME.chartText,fontSize:11}} interval={3} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip prefix="₹" suffix="M"/>} cursor={{fill:THEME.blueSoft}}/>
              <Area type="monotone" dataKey="volume" stroke={THEME.blue} fill="url(#hg)" strokeWidth={2} dot={false}/>
            </AreaChart>
          </ResponsiveContainer>
        </div>
      );
      case "state": return (
        <div style={cc}><p style={tt}>Volume by State (₹M)</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={stateChartData} margin={{top:10,right:10,bottom:0,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="state" tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip prefix="₹" suffix="M"/>} cursor={{fill:THEME.blueSoft}}/>
              <Bar dataKey="vol" fill={THEME.blueLight} radius={[4,4,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      case "category": return (
        <div style={cc}><p style={tt}>Transactions by Category</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={catChartData} margin={{top:10,right:10,bottom:0,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="name" tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip/>} cursor={{fill:THEME.blueSoft}}/>
              <Bar dataKey="txns" radius={[4,4,0,0]}>{catChartData.map((_,i)=><Cell key={i} fill={COLORS[i%COLORS.length]}/>)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      case "device_compare": return (
        <div style={cc}><p style={tt}>Device Avg Amount by Category (₹)</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={Object.entries(DATA.device_cat_avg).map(([cat,v])=>({cat,...v}))} margin={{top:10,right:10,bottom:10,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="cat" tick={{fill:THEME.chartText,fontSize:9}} angle={-20} textAnchor="end" axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip prefix="₹"/>} cursor={{fill:THEME.blueSoft}}/>
              <Bar dataKey="Android" fill={THEME.blue} radius={[2,2,0,0]}/>
              <Bar dataKey="iOS" fill={THEME.blueLight} radius={[2,2,0,0]}/>
              <Bar dataKey="Web" fill={THEME.accent} radius={[2,2,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      case "network": return (
        <div style={cc}><p style={tt}>Network Distribution & Fraud Rate</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={Object.entries(DATA.networks).map(([k,v])=>({name:k,txns:v,fraud:DATA.network_fraud[k]||0}))} margin={{top:10,right:10,bottom:0,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="name" tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <YAxis yAxisId="left" tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <YAxis yAxisId="right" orientation="right" tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <Tooltip/>
              <Bar yAxisId="left" dataKey="txns" fill={THEME.blue} radius={[4,4,0,0]}/>
              <Bar yAxisId="right" dataKey="fraud" fill={THEME.danger} radius={[4,4,0,0]} name="Fraud%"/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      case "bank": return (
        <div style={cc}><p style={tt}>Bank Transactions</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={bankChartData} margin={{top:10,right:10,bottom:0,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="bank" tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <Tooltip cursor={{fill:THEME.blueSoft}}/>
              <Bar dataKey="txns" fill={THEME.success} radius={[4,4,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      case "daily": return (
        <div style={cc}><p style={tt}>Daily Transaction Volume (₹M)</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={dailyChartData} margin={{top:10,right:10,bottom:0,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="day" tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip prefix="₹" suffix="M"/>} cursor={{fill:THEME.blueSoft}}/>
              <Bar dataKey="volume" fill={THEME.accent} radius={[4,4,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      case "age": return (
        <div style={cc}><p style={tt}>Age Group Distribution</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={Object.entries(DATA.age_groups).map(([k,v])=>({age:k,txns:v,avg:DATA.age_avg[k],fraud:DATA.age_fraud[k]}))} margin={{top:10,right:10,bottom:0,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="age" tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:11}} axisLine={false} tickLine={false}/>
              <Tooltip cursor={{fill:THEME.blueSoft}}/>
              <Bar dataKey="txns" fill={THEME.warning} radius={[4,4,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      case "txtype": return (
        <div style={cc}><p style={tt}>Transaction Types</p>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={Object.entries(DATA.tx_types).map(([k,v])=>({name:k,value:v}))} dataKey="value" cx="50%" cy="50%" outerRadius={80} innerRadius={40} label={({name,percent})=>`${name} ${(percent*100).toFixed(0)}%`} labelLine={false} fontSize={11}>
                {Object.keys(DATA.tx_types).map((_,i)=><Cell key={i} fill={COLORS[i]}/>)}
              </Pie>
              <Tooltip/>
            </PieChart>
          </ResponsiveContainer>
        </div>
      );
      case "fraud_overview": return (
        <div style={cc}><p style={tt}>Fraud Rate by Category (%)</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={Object.entries(DATA.cat_fraud).map(([k,v])=>({cat:k,rate:v})).sort((a,b)=>b.rate-a.rate)} margin={{top:10,right:10,bottom:0,left:-10}}>
              <CartesianGrid strokeDasharray="4 4" stroke={THEME.chartGrid} vertical={false}/>
              <XAxis dataKey="cat" tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <YAxis tick={{fill:THEME.chartText,fontSize:10}} axisLine={false} tickLine={false}/>
              <Tooltip content={<CustomTooltip suffix="%"/>} cursor={{fill:THEME.blueSoft}}/>
              <Bar dataKey="rate" fill={THEME.danger} radius={[4,4,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
      default: return null;
    }
  };

  // ── Markdown-lite renderer ────────────────────────────────────────────────
  const renderMessage = (content) => {
    const lines = content.split("\n");
    return lines.map((line,i)=>{
      if(line.startsWith("### ")) return <h3 key={i} style={{fontSize:14,fontWeight:700,color:THEME.textPrimary,margin:"12px 0 4px"}}>{line.slice(4)}</h3>;
      if(line.startsWith("## "))  return <h2 key={i} style={{fontSize:15,fontWeight:700,color:THEME.blue,margin:"12px 0 4px"}}>{line.slice(3)}</h2>;
      if(line.startsWith("**") && line.endsWith("**")) return <p key={i} style={{fontWeight:700,color:THEME.textPrimary,margin:"6px 0"}}>{line.slice(2,-2)}</p>;
      if(line.startsWith("- ") || line.startsWith("• ")) return <li key={i} style={{marginLeft:16,marginBottom:3,color:THEME.textSecondary,fontSize:13,lineHeight:1.6}}>{line.slice(2)}</li>;
      if(line.trim()==="") return <br key={i}/>;
      const bold = line.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>");
      return <p key={i} style={{margin:"3px 0",color:THEME.textSecondary,fontSize:13,lineHeight:1.7}} dangerouslySetInnerHTML={{__html:bold}}/>;
    });
  };

  // ── Tab config: Dashboard tab only visible after CSV upload ──────────────
  const tabs = [
    { id:"chat",      label:"💬 Chat" },
    ...(csvLoaded ? [{ id:"dashboard", label:"📊 Dashboard" }] : []),
  ];

  // ── Styles matching old.txt ───────────────────────────────────────────────
  const tabStyle = (active) => ({
    padding:"8px 20px", fontSize:13, fontWeight:600, cursor:"pointer",
    border:"none", background:"transparent",
    color: active ? THEME.blue : THEME.textSecondary,
    borderBottom: active ? `2px solid ${THEME.blue}` : "2px solid transparent",
    transition:"all 0.2s", position:"relative", top:1,
  });

  // ══════════════════════════════════════════════════════════════════════════
  return (
    <div style={{ height:"100vh", display:"flex", flexDirection:"column", background:THEME.bg, fontFamily:"-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif" }}>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.85)} 50%{opacity:1;transform:scale(1)} }
        @keyframes spin  { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        *{box-sizing:border-box; margin:0; padding:0}
        ul,ol{padding-left:0; list-style:none}
        ::-webkit-scrollbar{width:6px;height:6px}
        ::-webkit-scrollbar-track{background:#f1f5f9}
        ::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px}
        .dash-card:hover{transform:translateY(-2px)!important; box-shadow:0 10px 15px -3px rgba(0,0,0,0.05)!important; border-color:${THEME.blueSoft}!important;}
      `}</style>

      {/* ── HEADER ─────────────────────────────────────────────────────────── */}
      <div style={{ background:THEME.surface, borderBottom:`1px solid ${THEME.border}`, padding:"0 24px", height:60, display:"flex", alignItems:"center", justifyContent:"space-between", flexShrink:0, zIndex:100 }}>

        {/* Logo + Tabs */}
        <div style={{ display:"flex", alignItems:"center", gap:0 }}>
          <div style={{ display:"flex", alignItems:"center", gap:10, marginRight:28 }}>
            <div style={{ width:32, height:32, borderRadius:8, background:THEME.gradient, display:"flex", alignItems:"center", justifyContent:"center", color:"#fff", fontSize:16, fontWeight:700 }}>X</div>
            <div>
              <div style={{ fontSize:15, fontWeight:700, color:THEME.textPrimary }}>InsightX AI</div>
              <div style={{ fontSize:11, color:THEME.textSecondary }}>Leadership Analytics · UPI Transactions 2024</div>
            </div>
          </div>

          {/* Tab navigation — dashboard tab appears only after CSV upload */}
          <div style={{ display:"flex", gap:4, alignItems:"flex-end", height:60 }}>
            {tabs.map(t => (
              <button key={t.id} onClick={()=>setActiveTab(t.id)} style={tabStyle(activeTab===t.id)}>
                {t.label}
                {t.id==="dashboard" && activeTab!=="dashboard" && (
                  <span style={{ position:"absolute", top:10, right:10, width:6, height:6, borderRadius:"50%", background:THEME.success }}/>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Right controls */}
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          {/* Backend status */}
          <div style={{ display:"flex", alignItems:"center", gap:6, fontSize:11, color:backendStatus==="ok"?THEME.success:backendStatus==="error"?THEME.danger:THEME.textSecondary }}>
            <div style={{ width:7, height:7, borderRadius:"50%", background:backendStatus==="ok"?THEME.success:backendStatus==="error"?THEME.danger:THEME.textLight }}/>
            {backendStatus==="ok"?"Backend connected":backendStatus==="error"?"Backend offline":"Connecting…"}
          </div>
          {/* Upload CSV */}
          <button onClick={()=>fileInputRef.current?.click()} style={{
            padding:"6px 14px", borderRadius:8, border:`1px solid ${THEME.border}`,
            background: uploadStatus==="success" ? THEME.success : uploadStatus==="error" ? THEME.danger : THEME.surface,
            color: uploadStatus ? "#fff" : THEME.textPrimary,
            fontSize:12, fontWeight:600, cursor:"pointer", transition:"all 0.2s",
          }}>
            {uploadStatus==="uploading" ? "⏳ Uploading…" : uploadStatus==="success" ? "✓ Loaded!" : uploadStatus==="error" ? "✗ Error" : "📂 Upload CSV"}
          </button>
          <input ref={fileInputRef} type="file" accept=".csv" style={{display:"none"}} onChange={handleUpload}/>
          {/* New Chat */}
          <button onClick={newChat} style={{ padding:"6px 14px", borderRadius:8, border:`1px solid ${THEME.border}`, background:THEME.surface, color:THEME.textPrimary, fontSize:12, fontWeight:600, cursor:"pointer" }}>
            + New Chat
          </button>
        </div>
      </div>

      {/* ── BODY ───────────────────────────────────────────────────────────── */}
      <div style={{ flex:1, display:"flex", overflow:"hidden" }}>

        {/* ── CHAT TAB ─────────────────────────────────────────────────────── */}
        {activeTab==="chat" && (
          <>
            {/* Sidebar */}
            <div style={{ width:240, background:THEME.surface, borderRight:`1px solid ${THEME.border}`, padding:"16px 12px", overflowY:"auto", flexShrink:0 }}>
              <p style={{ fontSize:10, fontWeight:700, color:THEME.textLight, letterSpacing:1, textTransform:"uppercase", margin:"0 0 12px 4px" }}>Start by Asking</p>
              {SAMPLE_QUERIES.map((q,i) => (
                <button key={i} onClick={()=>sendMessage(q)} style={{ width:"100%", textAlign:"left", padding:"8px 10px", borderRadius:8, border:"none", background:"transparent", color:THEME.textSecondary, fontSize:12, cursor:"pointer", marginBottom:2, lineHeight:1.5, transition:"background 0.15s" }}
                  onMouseEnter={e=>e.target.style.background=THEME.surfaceHover}
                  onMouseLeave={e=>e.target.style.background="transparent"}>
                  {q}
                </button>
              ))}
              {/* Session info */}
              {sessionId && (
                <div style={{ marginTop:20, padding:"8px 10px", background:THEME.bluePale, borderRadius:8, fontSize:10, color:THEME.blue }}>
                  <div style={{ fontWeight:700, marginBottom:2 }}>Active Session</div>
                  <div style={{ wordBreak:"break-all", opacity:0.7 }}>{sessionId.slice(0,16)}…</div>
                </div>
              )}
              {/* CSV loaded hint */}
              {csvLoaded && (
                <div style={{ marginTop:12, padding:"8px 10px", background:"#f0fdf4", borderRadius:8, fontSize:10, color:THEME.success, border:`1px solid #bbf7d0` }}>
                  <div style={{ fontWeight:700, marginBottom:2 }}>📊 Dashboard ready</div>
                  <div style={{ opacity:0.8 }}>{dashData?.filename}</div>
                  <button onClick={()=>setActiveTab("dashboard")} style={{ marginTop:6, fontSize:10, color:THEME.success, background:"transparent", border:`1px solid ${THEME.success}`, borderRadius:4, padding:"2px 8px", cursor:"pointer", fontWeight:600 }}>View Dashboard →</button>
                </div>
              )}
            </div>

            {/* Chat area */}
            <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
              <div style={{ flex:1, overflowY:"auto", padding:"24px" }}>
                {messages.map((msg,i) => (
                  <div key={i} style={{ display:"flex", gap:12, marginBottom:20, justifyContent:msg.role==="user"?"flex-end":"flex-start" }}>
                    {msg.role==="assistant" && (
                      <div style={{ width:32, height:32, borderRadius:8, background:THEME.gradient, display:"flex", alignItems:"center", justifyContent:"center", color:"#fff", fontSize:13, fontWeight:700, flexShrink:0, marginTop:2 }}>X</div>
                    )}
                    <div style={{ maxWidth:"72%" }}>
                      <div style={{
                        background: msg.role==="user" ? THEME.blue : THEME.surface,
                        color: msg.role==="user" ? "#fff" : THEME.textPrimary,
                        padding:"12px 16px", borderRadius:12,
                        border: msg.role==="user" ? "none" : `1px solid ${THEME.border}`,
                        fontSize:13, lineHeight:1.7,
                      }}>
                        {msg.role==="user" ? msg.content : <div>{renderMessage(msg.content)}</div>}
                      </div>
                      {msg.chart && renderChart(msg.chart)}
                      {msg.confidence && (
                        <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:6, fontSize:11, color:THEME.textLight }}>
                          <div style={{ width:40, height:3, borderRadius:2, background:THEME.border, overflow:"hidden" }}>
                            <div style={{ height:"100%", width:`${msg.confidence.score}%`, background:msg.confidence.score>85?THEME.success:THEME.warning, borderRadius:2 }}/>
                          </div>
                          {msg.confidence.score}% confidence · {msg.confidence.label}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div style={{ display:"flex", gap:12, marginBottom:20 }}>
                    <div style={{ width:32, height:32, borderRadius:8, background:THEME.gradient, display:"flex", alignItems:"center", justifyContent:"center", color:"#fff", fontSize:13, fontWeight:700 }}>X</div>
                    <div style={{ background:THEME.surface, border:`1px solid ${THEME.border}`, borderRadius:12, padding:"12px 16px", display:"flex", gap:6, alignItems:"center" }}>
                      {[0,1,2].map(j=><div key={j} style={{ width:7, height:7, borderRadius:"50%", background:THEME.blue, animation:"pulse 1.2s infinite", animationDelay:`${j*0.2}s`, opacity:0.6 }}/>)}
                    </div>
                  </div>
                )}
                <div ref={chatEndRef}/>
              </div>

              {/* Input bar */}
              <div style={{ padding:"16px 24px", background:THEME.surface, borderTop:`1px solid ${THEME.border}` }}>
                <div style={{ display:"flex", gap:10, maxWidth:900, margin:"0 auto" }}>
                  <input
                    ref={inputRef} value={input}
                    onChange={e=>setInput(e.target.value)}
                    onKeyDown={e=>e.key==="Enter"&&!e.shiftKey&&sendMessage()}
                    placeholder={backendStatus==="error"?"⚠ Backend offline — start uvicorn first":"Ask anything …"}
                    disabled={loading || backendStatus==="error"}
                    style={{ flex:1, padding:"12px 16px", borderRadius:10, border:`1.5px solid ${THEME.border}`, background:THEME.bg, fontSize:14, color:THEME.textPrimary, outline:"none", transition:"border-color 0.2s" }}
                    onFocus={e=>e.target.style.borderColor=THEME.blue}
                    onBlur={e=>e.target.style.borderColor=THEME.border}
                  />
                  <button onClick={()=>sendMessage()} disabled={loading||!input.trim()||backendStatus==="error"}
                    style={{ padding:"12px 20px", borderRadius:10, border:"none", background:loading||!input.trim()?THEME.border:THEME.gradient, color:loading||!input.trim()?THEME.textLight:"#fff", fontSize:14, fontWeight:600, cursor:loading||!input.trim()?"not-allowed":"pointer", transition:"all 0.2s", minWidth:80 }}>
                    {loading?"…":"Send"}
                  </button>
                </div>
                <p style={{ textAlign:"center", fontSize:11, color:THEME.textLight, margin:"8px 0 0" }}>
                  Powered by @Coder-2026. All rights reserved.
                </p>
              </div>
            </div>
          </>
        )}

        {/* ── DASHBOARD TAB — only shown after CSV upload ───────────────────── */}
        {activeTab==="dashboard" && (
          dashLoading ? (
            /* Loading spinner */
            <div style={{ flex:1, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:16, background:THEME.bg }}>
              <div style={{ width:40, height:40, border:`3px solid ${THEME.blueSoft}`, borderTopColor:THEME.blue, borderRadius:"50%", animation:"spin 0.8s linear infinite" }}/>
              <div style={{ fontSize:14, color:THEME.textSecondary, fontWeight:500 }}>Computing dashboard insights…</div>
            </div>
          ) : dashData ? (
            /* Dynamic dashboard from uploaded CSV */
            <DynamicDashboard dash={dashData}/>
          ) : (
            /* Fallback — shouldn't normally reach here */
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", background:THEME.bg }}>
              <div style={{ textAlign:"center" }}>
                <div style={{ fontSize:48, marginBottom:16 }}>📂</div>
                <div style={{ fontSize:16, fontWeight:700, color:THEME.textPrimary, marginBottom:8 }}>No data loaded</div>
                <div style={{ fontSize:13, color:THEME.textSecondary, marginBottom:20 }}>Upload a CSV file to generate your dashboard</div>
                <button onClick={()=>fileInputRef.current?.click()} style={{ padding:"10px 24px", borderRadius:8, background:THEME.gradient, color:"#fff", border:"none", fontSize:14, fontWeight:600, cursor:"pointer" }}>Upload CSV</button>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}