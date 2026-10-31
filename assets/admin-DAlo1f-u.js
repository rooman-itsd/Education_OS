import{r as f,j as e,a as ea,g as na,l as ot,b as on,c as ta,A as Oe,p as qt,d as sa,e as aa,f as ia,h as ra,R as $t,P as Vt,i as Ht,k as oa,m as Be,n as la,o as da}from"./Badge-DPdjQx2J.js";import{_ as ca}from"./index-DspbCeIn.js";import{_ as ma}from"./index-DAVJmkz_.js";import{_ as pa}from"./index-DP2o49uf.js";import{_ as ua}from"./index-Bk2NycCz.js";import{_ as ga}from"./index-DXpBTIPY.js";import{_ as ha}from"./index-DRq2fPyq.js";import{_ as fa}from"./index-CGcjIDt-.js";import{_ as ya}from"./index-DrfVAjj6.js";import{_ as ba}from"./index-CYDgtq6C.js";import{_ as xa}from"./index-CXaHCDfm.js";import{_ as va}from"./index-Clr3_-NG.js";import{_ as wa}from"./index-B-5_3GdS.js";import{_ as ka}from"./index-DAUjl70b.js";import{_ as _a}from"./index-BMzxeHoK.js";import{_ as ja}from"./index-Cf0iQsKP.js";import{_ as Fa}from"./index-CH4H0J5L.js";import{_ as Na}from"./index-BNRXxWh_.js";import{_ as Sa}from"./index-CkeNuV32.js";import{_ as Ea}from"./index-BWJntc6t.js";import{_ as Aa}from"./index-CAg0FU6O.js";import{_ as Ca}from"./index-NLgkZ1Ro.js";import{_ as Pa}from"./index-D1pXMdn9.js";import{_ as Ra}from"./index-DHrpiO6j.js";import{_ as Ma}from"./index-CW3v0sBp.js";import{_ as Da}from"./index-11G3VY4O.js";import{_ as Oa}from"./index-Di5wBbtj.js";import{_ as Ta}from"./index-Dsm3YnyJ.js";import{_ as Ba}from"./index-vG-bqEJY.js";import{_ as La}from"./index-9j79eqzL.js";import{_ as Ia}from"./index-Dd7dEWin.js";import{_ as qa}from"./index-Cg2Z_m8G.js";import{_ as $a}from"./index-Bvj13iz6.js";import{_ as Va}from"./index-BskL9t9_.js";import{_ as Ha}from"./index-hb_7jGLY.js";import{_ as Ua}from"./index-DLE-GP32.js";import{_ as Ga}from"./index-AejmBxQ8.js";import{_ as Wa}from"./index-CimVYWbz.js";import{_ as Ya}from"./index-CIe7p7JQ.js";import{_ as za}from"./index-VORS1qnT.js";import{_ as Ka}from"./index-B-p0JPm7.js";import{_ as Qa}from"./index-W0b8TDjS.js";import{_ as Ja}from"./index-DjKAWLCd.js";import"./ListRow-De3l5eYv.js";import"./Progress-BaoDe-W6.js";function Ut(){const n=window.location.hash.replace(/^#/,"")||"/",t=n.indexOf("?"),s=(t===-1?n:n.slice(0,t))||"/";return{pathname:s.startsWith("/")?s:`/${s}`,search:t===-1?"":n.slice(t)}}let lt=Ut(),dt=window.location.hash;function Xa(){return window.location.hash!==dt&&(dt=window.location.hash,lt=Ut()),lt}function Za(n){return window.addEventListener("hashchange",n),()=>window.removeEventListener("hashchange",n)}function jn(n,t=!1){const s=new URL(window.location.href);s.hash=n,t?window.history.replaceState(null,"",s):window.history.pushState(null,"",s),window.dispatchEvent(new HashChangeEvent("hashchange"))}const Gt=f.createContext(null),Ge=f.createContext({params:{},outlet:null});function ei({children:n}){const t=f.useSyncExternalStore(Za,Xa);return e.jsx(Gt.Provider,{value:t,children:n})}function $e(){const n=f.useContext(Gt);if(!n)throw new Error("useLocation() must be used inside <BrowserRouter>");return n}function Fn(){return f.useCallback((n,t)=>jn(n,t==null?void 0:t.replace),[])}function ni(){return f.useContext(Ge).params}function Wt(){const{pathname:n,search:t}=$e(),s=f.useMemo(()=>new URLSearchParams(t),[t]),i=f.useCallback(a=>jn(`${n}?${new URLSearchParams(a).toString()}`),[n]);return[s,i]}function Yt(){return e.jsx(e.Fragment,{children:f.useContext(Ge).outlet})}function Bn({to:n,replace:t}){return f.useLayoutEffect(()=>jn(n,t),[n,t]),null}function Q(n){return null}function ti(n,t){if(n==="*")return{};const s=n.split("/").filter(Boolean),i=t.split("/").filter(Boolean);if(s.length!==i.length)return null;const a={};for(let o=0;o<s.length;o++){const m=s[o],p=decodeURIComponent(i[o]);if(m.startsWith(":"))a[m.slice(1)]=p;else if(m!==p)return null}return a}function zt(n,t){for(const s of f.Children.toArray(n)){if(!f.isValidElement(s))continue;const{path:i,element:a,children:o}=s.props;if(i===void 0){const p=zt(o,t);if(p!==void 0)return e.jsx(si,{element:a,outlet:p});continue}const m=ti(i,t);if(m)return e.jsx(Ge.Provider,{value:{params:m,outlet:null},children:a})}}function si({element:n,outlet:t}){const s=f.useContext(Ge);return e.jsx(Ge.Provider,{value:{params:s.params,outlet:t},children:n})}function ai({children:n}){const{pathname:t}=$e();return e.jsx(e.Fragment,{children:zt(n,t)??null})}function X({to:n,replace:t,onClick:s,target:i,...a}){const o=m=>{s==null||s(m),!(m.defaultPrevented||m.button!==0||i||m.metaKey||m.altKey||m.ctrlKey||m.shiftKey)&&(m.preventDefault(),jn(n,t))};return e.jsx("a",{href:`#${n}`,onClick:o,target:i,...a})}function ct({className:n,...t}){const{pathname:s}=$e(),i=t.to.split("?")[0],a=s===i||i!=="/"&&s.startsWith(`${i}/`),o=a?[n,"active"].filter(Boolean).join(" "):n;return e.jsx(X,{"aria-current":a?"page":void 0,className:o,...t})}const Ln="eos.admin.preview",Kt=f.createContext(null),mt=n=>n.me.is_super_admin||n.me.roles.includes("org-admin");function ii(n){return n instanceof Oe?n.message.includes("pending_approval")?"Your organisation's academic package is waiting for platform approval. Try again once you receive the approval email.":n.status===401?"Incorrect email or password.":n.status===422?"Enter your institutional email address.":n.message:n instanceof Error?n.message:String(n)}function ri(){try{return sessionStorage.getItem(Ln)==="1"}catch{return!1}}function pt(n){try{n?sessionStorage.setItem(Ln,"1"):sessionStorage.removeItem(Ln)}catch{}}function oi({children:n}){const[t,s]=f.useState("loading"),[i,a]=f.useState(!1),[o,m]=f.useState(null);f.useEffect(()=>{let u=!0;return(async()=>{if(new URLSearchParams(window.location.search).get("preview")==="1"||!await ea()){if(!u)return;a(!0),s(ri()?"signed-in":"signed-out");return}if(!na()){u&&s("signed-out");return}try{const h=await ot();if(!u)return;mt(h)?(m(h),s("signed-in")):(on(),s("signed-out"))}catch{on(),u&&s("signed-out")}})(),()=>{u=!1}},[]);const p=f.useCallback(async(u,k)=>{if(i){pt(!0),s("signed-in");return}await ta(u,k);const h=await ot();if(!mt(h))throw on(),new Error("This account is not an administrator. Sign in with a super admin or organisation admin account.");m(h),s("signed-in")},[i]),g=f.useCallback(()=>{on(),pt(!1),m(null),s("signed-out")},[]);return e.jsx(Kt.Provider,{value:{status:t,preview:i,session:o,signIn:p,signOut:g},children:n})}function me(){const n=f.useContext(Kt);if(!n)throw new Error("useAuth() must be used inside <AuthProvider>");return n}const li="/assets/academics-Ch7j_ZP9.jpg",di="/assets/admissions-DHoK_xvv.jpg",ci="/assets/alumni-DwMt1H0B.jpg",mi="/assets/assets-fnyAynY0.jpg",pi="/assets/athletes-8ToCgm8p.jpg",ui="/assets/budget-B6tm1sOF.jpg",gi="/assets/campus-mOCHWIV4.jpg",hi="/assets/e-office-iDVMvSXz.jpg",fi="/assets/enrolment-BQGT5R_F.jpg",yi="/assets/eos-emblem-Cbb_MR42.png",bi="/assets/eos-logo-D5-Gnv0d.png",xi="/assets/examinations-DnnAb6ni.jpg",vi="/assets/facilities-BD_W5ucA.jpg",wi="/assets/facility-booking-BWpWFtCt.jpg",ki="/assets/favicon-364ohylp.png",_i="/assets/fees-GArltPur.jpg",ji="/assets/field-training-CIbir7Cz.jpg",Fi="/assets/grievance-D8heymOF.jpg",Ni="/assets/hostel-BwZVL_fL.jpg",Si="/assets/hr-payroll-o3oC7Mr8.jpg",Ei="/assets/inventory-B1YqfEvF.jpg",Ai="/assets/iqac-accreditation-QnFSqfHe.jpg",Ci="/assets/library-DrZsMz4I.jpg",Pi="/assets/lms-DjU532uj.jpg",Ri="/assets/maintenance-RCDA5RCB.jpg",Mi="/assets/nutrition-B5ZlJdOl.jpg",Di="/assets/placement-career-Bl0QnJuG.jpg",Oi="/assets/portfolio-v3-BdwymtLO.jpg",Ti="/assets/procurement-DFh-_lVc.jpg",Bi="/assets/productions-CbRKzsjA.jpg",Li="/assets/projects-v2-DjSTnGW-.jpg",Ii="/assets/rti-aioYs8Gz.jpg",qi="/assets/selection-process-BmyHNliD.jpg",$i="/assets/skill-progress-nBwaRVRY.jpg",Vi="/assets/students-itOF3-0Z.jpg",Hi="/assets/timetable-Ba4peqRM.jpg",Ui="/assets/tournaments-03rqgGGp.jpg",Gi="/assets/training-C1GnZ0YI.jpg",Wi="/assets/transport-5ZqoBr-J.jpg",Yi="/assets/web-portal-Bm0MxC8O.jpg",zi=Object.assign({"../assets/academics.jpg":li,"../assets/admissions.jpg":di,"../assets/alumni.jpg":ci,"../assets/assets.jpg":mi,"../assets/athletes.jpg":pi,"../assets/budget.jpg":ui,"../assets/campus.jpg":gi,"../assets/e-office.jpg":hi,"../assets/enrolment.jpg":fi,"../assets/eos-emblem.png":yi,"../assets/eos-logo.png":bi,"../assets/examinations.jpg":xi,"../assets/facilities.jpg":vi,"../assets/facility-booking.jpg":wi,"../assets/favicon.png":ki,"../assets/fees.jpg":_i,"../assets/field-training.jpg":ji,"../assets/grievance.jpg":Fi,"../assets/hostel.jpg":Ni,"../assets/hr-payroll.jpg":Si,"../assets/inventory.jpg":Ei,"../assets/iqac-accreditation.jpg":Ai,"../assets/library.jpg":Ci,"../assets/lms.jpg":Pi,"../assets/maintenance.jpg":Ri,"../assets/nutrition.jpg":Mi,"../assets/placement-career.jpg":Di,"../assets/portfolio-v3.jpg":Oi,"../assets/procurement.jpg":Ti,"../assets/productions.jpg":Bi,"../assets/projects-v2.jpg":Li,"../assets/rti.jpg":Ii,"../assets/selection-process.jpg":qi,"../assets/skill-progress.jpg":$i,"../assets/students.jpg":Vi,"../assets/timetable.jpg":Hi,"../assets/tournaments.jpg":Ui,"../assets/training.jpg":Gi,"../assets/transport.jpg":Wi,"../assets/web-portal.jpg":Yi});function B(n){const t=zi[`../assets/${n.replace(/^\//,"")}`];if(!t)throw new Error(`missing admin asset: ${n}`);return t}const Ki=n=>Object.keys(n).some(t=>t.startsWith("aria-")||t==="role"||t==="title");function N(n,t){const s=f.forwardRef(({color:i,size:a,width:o,height:m,strokeWidth:p,absoluteStrokeWidth:g,className:u="",children:k,...h},l)=>{const y=o??a??24,v=m??a??24,x=g?Number(p??2)*24/Number(a??o??24):p??2,F=["lucide",`lucide-${n}`,...u.split(" ")].filter((E,A,b)=>E.trim()!==""&&b.indexOf(E)===A);return f.createElement("svg",{ref:l,xmlns:"http://www.w3.org/2000/svg",width:y,height:v,viewBox:"0 0 24 24",fill:"none",stroke:i||"currentColor",strokeWidth:x,strokeLinecap:"round",strokeLinejoin:"round",className:F.join(" "),...k||Ki(h)?{}:{"aria-hidden":"true"},...h},...t.map(([E,A],b)=>f.createElement(E,{key:b,...A})),k)});return s.displayName=n,s}const In=N("activity",[["path",{d:"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"}]]),Ze=N("triangle-alert",[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"}],["path",{d:"M12 9v4"}],["path",{d:"M12 17h.01"}]]),Qi=N("apple",[["path",{d:"M12 6.528V3a1 1 0 0 1 1-1h0"}],["path",{d:"M18.237 21A15 15 0 0 0 22 11a6 6 0 0 0-10-4.472A6 6 0 0 0 2 11a15.1 15.1 0 0 0 3.763 10 3 3 0 0 0 3.648.648 5.5 5.5 0 0 1 5.178 0A3 3 0 0 0 18.237 21"}]]),Fe=N("arrow-right",[["path",{d:"M5 12h14"}],["path",{d:"m12 5 7 7-7 7"}]]),Ji=N("award",[["path",{d:"m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"}],["circle",{cx:"12",cy:"8",r:"6"}]]),Xi=N("badge-check",[["path",{d:"M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"}],["path",{d:"m16 9-5.5 5.5L8 12"}]]),Qt=N("bell",[["path",{d:"M10.268 21a2 2 0 0 0 3.464 0"}],["path",{d:"M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"}]]),pn=N("blocks",[["path",{d:"M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2"}],["rect",{x:"14",y:"2",width:"8",height:"8",rx:"1"}]]),Zi=N("book-bookmark",[["path",{d:"M10 2v7.751a.25.25 0 00.407.195l2.28-1.834a.5.5 0 01.627 0l2.28 1.834A.25.25 0 0016 9.751V2"}],["path",{d:"M4 19.5v-15A2.5 2.5 0 016.5 2H19a1 1 0 011 1v18a1 1 0 01-1 1H6.5a1 1 0 010-5H20"}]]),Yn=N("book-open",[["path",{d:"M12 5v16"}],["path",{d:"M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z"}]]),Jt=N("boxes",[["path",{d:"M2.97 12.92A2 2 0 0 0 2 14.63v3.24a2 2 0 0 0 .97 1.71l3 1.8a2 2 0 0 0 2.06 0L12 19v-5.5l-5-3-4.03 2.42Z"}],["path",{d:"m7 16.5-4.74-2.85"}],["path",{d:"m7 16.5 5-3"}],["path",{d:"M7 16.5v5.17"}],["path",{d:"M12 13.5V19l3.97 2.38a2 2 0 0 0 2.06 0l3-1.8a2 2 0 0 0 .97-1.71v-3.24a2 2 0 0 0-.97-1.71L17 10.5l-5 3Z"}],["path",{d:"m17 16.5-5-3"}],["path",{d:"m17 16.5 4.74-2.85"}],["path",{d:"M17 16.5v5.17"}],["path",{d:"M7.97 4.42A2 2 0 0 0 7 6.13v4.37l5 3 5-3V6.13a2 2 0 0 0-.97-1.71l-3-1.8a2 2 0 0 0-2.06 0l-3 1.8Z"}],["path",{d:"M12 8 7.26 5.15"}],["path",{d:"m12 8 4.74-2.85"}],["path",{d:"M12 13.5V8"}]]),er=N("briefcase",[["path",{d:"M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"}],["rect",{width:"20",height:"14",x:"2",y:"6",rx:"2"}]]),nr=N("building",[["path",{d:"M12 10h.01"}],["path",{d:"M12 14h.01"}],["path",{d:"M12 6h.01"}],["path",{d:"M16 10h.01"}],["path",{d:"M16 14h.01"}],["path",{d:"M16 6h.01"}],["path",{d:"M8 10h.01"}],["path",{d:"M8 14h.01"}],["path",{d:"M8 6h.01"}],["path",{d:"M9 22v-3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3"}],["rect",{x:"4",y:"2",width:"16",height:"20",rx:"2"}]]),Me=N("building-complex",[["path",{d:"M10 12h4"}],["path",{d:"M10 8h4"}],["path",{d:"M14 21v-3a2 2 0 0 0-4 0v3"}],["path",{d:"M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2"}],["path",{d:"M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"}]]),tr=N("bus",[["path",{d:"M8 6v6"}],["path",{d:"M15 6v6"}],["path",{d:"M2 12h19.6"}],["path",{d:"M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3"}],["circle",{cx:"7",cy:"18",r:"2"}],["path",{d:"M9 18h5"}],["circle",{cx:"16",cy:"18",r:"2"}]]),sr=N("calendar-check-2",[["path",{d:"M 19 3 L 5 3"}],["path",{d:"M 21 13 L 21 5"}],["path",{d:"M 21 5 A2 2 0 0 0 19 3"}],["path",{d:"M 3 19 A2 2 0 0 0 5 21"}],["path",{d:"M 3 5 L 3 19"}],["path",{d:"M 5 3 A2 2 0 0 0 3 5"}],["path",{d:"m16 19 2 2 4-4"}],["path",{d:"M16 2v3"}],["path",{d:"M3 9h18"}],["path",{d:"M5 21 L12.5 21"}],["path",{d:"M8 2v3"}]]),ar=N("calendar-range",[["rect",{x:"3",y:"3",width:"18",height:"18",rx:"2"}],["path",{d:"M16 2v3"}],["path",{d:"M3 9h18"}],["path",{d:"M8 2v3"}],["path",{d:"M17 13h-6"}],["path",{d:"M13 17H7"}],["path",{d:"M7 13h.01"}],["path",{d:"M17 17h.01"}]]),We=N("check",[["path",{d:"M20 6 9 17l-5-5"}]]),Z=N("circle-check",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m16 9-5.5 5.5L8 12"}]]),en=N("chevron-down",[["path",{d:"m6 9 6 6 6-6"}]]),ir=N("chevron-left",[["path",{d:"m15 18-6-6 6-6"}]]),Xt=N("chevron-right",[["path",{d:"m9 18 6-6-6-6"}]]),rr=N("clipboard-list",[["rect",{width:"8",height:"4",x:"8",y:"2",rx:"1",ry:"1"}],["path",{d:"M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"}],["path",{d:"M12 11h4"}],["path",{d:"M12 16h4"}],["path",{d:"M8 11h.01"}],["path",{d:"M8 16h.01"}]]),nn=N("clock",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M12 6v6l4 2"}]]),or=N("cpu",[["path",{d:"M12 20v2"}],["path",{d:"M12 2v2"}],["path",{d:"M17 20v2"}],["path",{d:"M17 2v2"}],["path",{d:"M2 12h2"}],["path",{d:"M2 17h2"}],["path",{d:"M2 7h2"}],["path",{d:"M20 12h2"}],["path",{d:"M20 17h2"}],["path",{d:"M20 7h2"}],["path",{d:"M7 20v2"}],["path",{d:"M7 2v2"}],["rect",{x:"4",y:"4",width:"16",height:"16",rx:"2"}],["rect",{x:"8",y:"8",width:"8",height:"8",rx:"1"}]]),lr=N("credit-card",[["rect",{width:"20",height:"14",x:"2",y:"5",rx:"2"}],["line",{x1:"2",x2:"22",y1:"10",y2:"10"}],["path",{d:"M6 14h2"}]]),zn=N("download",[["path",{d:"M12 15V3"}],["path",{d:"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}],["path",{d:"m7 10 5 5 5-5"}]]),dr=N("cloud-download",[["path",{d:"M12 13v8l-4-4"}],["path",{d:"m12 21 4-4"}],["path",{d:"M4.393 15.269A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.436 8.284"}]]),cr=N("dumbbell",[["path",{d:"M17.596 12.768a2 2 0 1 0 2.829-2.829l-1.768-1.767a2 2 0 0 0 2.828-2.829l-2.828-2.828a2 2 0 0 0-2.829 2.828l-1.767-1.768a2 2 0 1 0-2.829 2.829z"}],["path",{d:"m2.5 21.5 1.4-1.4"}],["path",{d:"m20.1 3.9 1.4-1.4"}],["path",{d:"M5.343 21.485a2 2 0 1 0 2.829-2.828l1.767 1.768a2 2 0 1 0 2.829-2.829l-6.364-6.364a2 2 0 1 0-2.829 2.829l1.768 1.767a2 2 0 0 0-2.828 2.829z"}],["path",{d:"m9.6 14.4 4.8-4.8"}]]),mr=N("eye-off",[["path",{d:"M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"}],["path",{d:"M14.084 14.158a3 3 0 0 1-4.242-4.242"}],["path",{d:"M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"}],["path",{d:"m2 2 20 20"}]]),tn=N("file-check-corner",[["path",{d:"M10.5 22H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v6"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"m14 20 2 2 4-4"}]]),An=N("file-clock",[["path",{d:"M16 22h2a2 2 0 0 0 2-2V8a2.4 2.4 0 0 0-.706-1.706l-3.588-3.588A2.4 2.4 0 0 0 14 2H6a2 2 0 0 0-2 2v2.85"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"M8 14v2.2l1.6 1"}],["circle",{cx:"8",cy:"16",r:"6"}]]),un=N("file-code-corner",[["path",{d:"M4 12.15V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2h-3.35"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"m5 16-3 3 3 3"}],["path",{d:"m9 22 3-3-3-3"}]]),pr=N("file-text",[["path",{d:"M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"M10 9H8"}],["path",{d:"M16 13H8"}],["path",{d:"M16 17H8"}]]),ur=N("folder-open",[["path",{d:"m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"}]]),gr=N("globe",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"}],["path",{d:"M2 12h20"}]]),Ye=N("graduation-cap",[["path",{d:"M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"}],["path",{d:"M22 10v6"}],["path",{d:"M6 12.5V16a6 3 0 0 0 12 0v-3.5"}]]),qn=N("hammer",[["path",{d:"m15 12-9.373 9.373a1 1 0 0 1-3.001-3L12 9"}],["path",{d:"m18 15 4-4"}],["path",{d:"m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172v-.344a2 2 0 0 0-.586-1.414l-1.657-1.657A6 6 0 0 0 12.516 3H9l1.243 1.243A6 6 0 0 1 12 8.485V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5"}]]),hr=N("handshake",[["path",{d:"m11 17 2 2a1 1 0 1 0 3-3"}],["path",{d:"m14 14 2.5 2.5a1 1 0 1 0 3-3l-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4"}],["path",{d:"m21 3 1 11h-2"}],["path",{d:"M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3"}],["path",{d:"M3 4h8"}]]),fr=N("circle-question-mark",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"}],["path",{d:"M12 17h.01"}]]),Zt=N("rotate-ccw-clock",[["path",{d:"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"}],["path",{d:"M3 3v5h5"}],["path",{d:"M12 7v5l4 2"}]]),es=N("house",[["path",{d:"M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"}],["path",{d:"M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"}]]),$n=N("indian-rupee",[["path",{d:"M6 3h12"}],["path",{d:"M6 8h12"}],["path",{d:"m6 13 8.5 8"}],["path",{d:"M6 13h3"}],["path",{d:"M9 13c6.667 0 6.667-10 0-10"}]]),Pe=N("key-round",[["path",{d:"M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"}],["circle",{cx:"16.5",cy:"7.5",r:".5",fill:"currentColor"}]]),yr=N("landmark",[["path",{d:"M10 18v-7"}],["path",{d:"M11.119 2.205a2 2 0 0 1 1.762 0l7.84 3.846A.5.5 0 0 1 20.5 7h-17a.5.5 0 0 1-.22-.949z"}],["path",{d:"M14 18v-7"}],["path",{d:"M18 18v-7"}],["path",{d:"M3 22h18"}],["path",{d:"M6 18v-7"}]]),ns=N("layers",[["path",{d:"M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"}],["path",{d:"M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"}],["path",{d:"M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"}]]),br=N("layout-dashboard",[["rect",{width:"7",height:"9",x:"3",y:"3",rx:"1"}],["rect",{width:"7",height:"5",x:"14",y:"3",rx:"1"}],["rect",{width:"7",height:"9",x:"14",y:"12",rx:"1"}],["rect",{width:"7",height:"5",x:"3",y:"16",rx:"1"}]]),Le=N("layout-grid",[["rect",{width:"7",height:"7",x:"3",y:"3",rx:"1"}],["rect",{width:"7",height:"7",x:"14",y:"3",rx:"1"}],["rect",{width:"7",height:"7",x:"14",y:"14",rx:"1"}],["rect",{width:"7",height:"7",x:"3",y:"14",rx:"1"}]]),xr=N("library",[["path",{d:"m16 6 4 14"}],["path",{d:"M12 6v14"}],["path",{d:"M8 8v12"}],["path",{d:"M4 4v16"}]]),Nn=N("life-buoy",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m4.93 4.93 4.24 4.24"}],["path",{d:"m14.83 9.17 4.24-4.24"}],["path",{d:"m14.83 14.83 4.24 4.24"}],["path",{d:"m9.17 14.83-4.24 4.24"}],["circle",{cx:"12",cy:"12",r:"4"}]]),ts=N("lock",[["rect",{width:"18",height:"11",x:"3",y:"11",rx:"2",ry:"2"}],["path",{d:"M7 11V7a5 5 0 0 1 10 0v4"}]]),ss=N("log-out",[["path",{d:"m16 17 5-5-5-5"}],["path",{d:"M21 12H9"}],["path",{d:"M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"}]]),vr=N("medal",[["path",{d:"M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"}],["path",{d:"M11 12 5.12 2.2"}],["path",{d:"m13 12 5.88-9.8"}],["path",{d:"M8 7h8"}],["circle",{cx:"12",cy:"17",r:"5"}],["path",{d:"M12 18v-2h-.5"}]]),wr=N("megaphone",[["path",{d:"M11 6a13 13 0 0 0 8.4-2.8A1 1 0 0 1 21 4v12a1 1 0 0 1-1.6.8A13 13 0 0 0 11 14H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z"}],["path",{d:"M6 14a12 12 0 0 0 2.4 7.2 2 2 0 0 0 3.2-2.4A8 8 0 0 1 10 14"}],["path",{d:"M8 6v8"}]]),kr=N("menu",[["path",{d:"M4 5h16"}],["path",{d:"M4 12h16"}],["path",{d:"M4 19h16"}]]),_r=N("monitor-play",[["path",{d:"M15.033 9.44a.647.647 0 0 1 0 1.12l-4.065 2.352a.645.645 0 0 1-.968-.56V7.648a.645.645 0 0 1 .967-.56z"}],["path",{d:"M12 17v4"}],["path",{d:"M8 21h8"}],["rect",{x:"2",y:"3",width:"20",height:"14",rx:"2"}]]),jr=N("package",[["path",{d:"M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"}],["path",{d:"M12 22V12"}],["polyline",{points:"3.29 7 12 12 20.71 7"}],["path",{d:"m7.5 4.27 9 5.15"}]]),Fr=N("chart-pie",[["path",{d:"M21 12c.552 0 1.005-.449.95-.998a10 10 0 0 0-8.953-8.951c-.55-.055-.998.398-.998.95v8a1 1 0 0 0 1 1z"}],["path",{d:"M21.21 15.89A10 10 0 1 1 8 2.83"}]]),Nr=N("plug",[["path",{d:"M12 22v-5"}],["path",{d:"M15 8V2"}],["path",{d:"M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z"}],["path",{d:"M9 8V2"}]]),as=N("plus",[["path",{d:"M5 12h14"}],["path",{d:"M12 5v14"}]]),Vn=N("power",[["path",{d:"M12 2v10"}],["path",{d:"M18.4 6.6a9 9 0 1 1-12.77.04"}]]),Sr=N("power-off",[["path",{d:"M18.36 6.64A9 9 0 0 1 20.77 15"}],["path",{d:"M6.16 6.16a9 9 0 1 0 12.68 12.68"}],["path",{d:"M12 2v4"}],["path",{d:"m2 2 20 20"}]]),is=N("presentation",[["path",{d:"M2 3h20"}],["path",{d:"M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"}],["path",{d:"m7 21 5-5 5 5"}]]),Er=N("refresh-cw",[["path",{d:"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"}],["path",{d:"M21 3v5h-5"}],["path",{d:"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"}],["path",{d:"M8 16H3v5"}]]);N("rotate-ccw",[["path",{d:"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"}],["path",{d:"M3 3v5h5"}]]);const ut=N("save",[["path",{d:"M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"}],["path",{d:"M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"}],["path",{d:"M7 3v4a1 1 0 0 0 1 1h7"}]]),Kn=N("scale",[["path",{d:"M12 3v18"}],["path",{d:"m19 8 3 8a5 5 0 0 1-6 0zV7"}],["path",{d:"M3 7h1a17 17 0 0 0 8-2 17 17 0 0 0 8 2h1"}],["path",{d:"m5 8 3 8a5 5 0 0 1-6 0zV7"}],["path",{d:"M7 21h10"}]]),Ar=N("scroll-text",[["path",{d:"M15 12h-5"}],["path",{d:"M15 8h-5"}],["path",{d:"M19 17V5a2 2 0 0 0-2-2H4"}],["path",{d:"M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"}]]),ye=N("search",[["path",{d:"m21 21-4.34-4.34"}],["circle",{cx:"11",cy:"11",r:"8"}]]),be=N("shield",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}]]),rs=N("shield-alert",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["path",{d:"M12 8v4"}],["path",{d:"M12 16h.01"}]]),ze=N("shield-check",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["path",{d:"m9 12 2 2 4-4"}]]),Cr=N("shopping-bag",[["path",{d:"M16 10a4 4 0 0 1-8 0"}],["path",{d:"M3.103 6.034h17.794"}],["path",{d:"M3.4 5.467a2 2 0 0 0-.4 1.2V20a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6.667a2 2 0 0 0-.4-1.2l-2-2.667A2 2 0 0 0 17 2H7a2 2 0 0 0-1.6.8z"}]]),Pr=N("siren",[["path",{d:"M7 18v-6a5 5 0 1 1 10 0v6"}],["path",{d:"M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z"}],["path",{d:"M21 12h1"}],["path",{d:"M18.5 4.5 18 5"}],["path",{d:"M2 12h1"}],["path",{d:"M12 2v1"}],["path",{d:"m4.929 4.929.707.707"}],["path",{d:"M12 12v6"}]]),Rr=N("timer",[["line",{x1:"10",x2:"14",y1:"2",y2:"2"}],["line",{x1:"12",x2:"15",y1:"14",y2:"11"}],["circle",{cx:"12",cy:"14",r:"8"}]]),os=N("trending-up",[["path",{d:"M16 7h6v6"}],["path",{d:"m22 7-8.5 8.5-5-5L2 17"}]]),Ke=N("trophy",[["path",{d:"M10 14.66V17a1 1 0 0 1-1 1 2 2 0 0 0-2 2v2"}],["path",{d:"M14 14.66V17a1 1 0 0 0 1 1 2 2 0 0 1 2 2v2"}],["path",{d:"M17.916 10H19.5A2.5 2.5 0 0 0 22 7.5V5a1 1 0 0 0-1-1h-3"}],["path",{d:"M4 22h16"}],["path",{d:"M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z"}],["path",{d:"M6.084 10H4.5A2.5 2.5 0 0 1 2 7.5V5a1 1 0 0 1 1-1h3"}]]),ls=N("user",[["path",{d:"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"}],["circle",{cx:"12",cy:"7",r:"4"}]]),ds=N("user-check",[["path",{d:"m16 11 2 2 4-4"}],["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}]]),Mr=N("user-cog",[["path",{d:"M10 15H6a4 4 0 0 0-4 4v2"}],["path",{d:"m14.305 16.53.923-.382"}],["path",{d:"m15.228 13.852-.923-.383"}],["path",{d:"m16.852 12.228-.383-.923"}],["path",{d:"m16.852 17.772-.383.924"}],["path",{d:"m19.148 12.228.383-.923"}],["path",{d:"m19.53 18.696-.382-.924"}],["path",{d:"m20.772 13.852.924-.383"}],["path",{d:"m20.772 16.148.924.383"}],["circle",{cx:"18",cy:"15",r:"3"}],["circle",{cx:"9",cy:"7",r:"4"}]]),Dr=N("user-plus",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}],["line",{x1:"19",x2:"19",y1:"8",y2:"14"}],["line",{x1:"22",x2:"16",y1:"11",y2:"11"}]]),Or=N("user-x",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}],["line",{x1:"17",x2:"22",y1:"8",y2:"13"}],["line",{x1:"22",x2:"17",y1:"8",y2:"13"}]]),sn=N("users",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["path",{d:"M16 3.128a4 4 0 0 1 0 7.744"}],["path",{d:"M22 21v-2a4 4 0 0 0-3-3.87"}],["circle",{cx:"9",cy:"7",r:"4"}]]),Tr=N("users-round",[["path",{d:"M18 21a8 8 0 0 0-16 0"}],["circle",{cx:"10",cy:"8",r:"5"}],["path",{d:"M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"}]]),Br=N("video",[["path",{d:"m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"}],["rect",{x:"2",y:"6",width:"14",height:"12",rx:"2"}]]),cs=N("wallet",[["path",{d:"M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"}],["path",{d:"M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"}]]),Lr=N("wrench",[["path",{d:"M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z"}]]),ie=N("x",[["path",{d:"M18 6 6 18"}],["path",{d:"m6 6 12 12"}]]),ms=N("circle-x",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m15 9-6 6"}],["path",{d:"m9 9 6 6"}]]),Ir=N("camera",[["path",{d:"M13.997 4a2 2 0 0 1 1.76 1.05l.486.9A2 2 0 0 0 18.003 7H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1.997a2 2 0 0 0 1.759-1.048l.489-.904A2 2 0 0 1 10.004 4z"}],["circle",{cx:"12",cy:"13",r:"3"}]]),qr=N("upload",[["path",{d:"M12 3v12"}],["path",{d:"m17 8-5-5-5 5"}],["path",{d:"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}]]),$r=N("trash",[["path",{d:"M10 11v6"}],["path",{d:"M14 11v6"}],["path",{d:"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"}],["path",{d:"M3 6h18"}],["path",{d:"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"}]]),gt=N("pencil",[["path",{d:"M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"}],["path",{d:"m15 5 4 4"}]]),Vr=N("mail",[["path",{d:"m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"}],["rect",{x:"2",y:"4",width:"20",height:"16",rx:"2"}]]);N("phone",[["path",{d:"M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"}]]);N("map-pin",[["path",{d:"M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"}],["circle",{cx:"12",cy:"10",r:"3"}]]);const Hr=N("smartphone",[["rect",{width:"14",height:"20",x:"5",y:"2",rx:"2",ry:"2"}],["path",{d:"M12 18h.01"}]]),Ur=N("languages",[["path",{d:"m5 8 6 6"}],["path",{d:"m4 14 6-6 2-3"}],["path",{d:"M2 5h12"}],["path",{d:"M7 2h1"}],["path",{d:"m22 22-5-10-5 10"}],["path",{d:"M14 18h6"}]]),Gr=N("palette",[["path",{d:"M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z"}],["circle",{cx:"13.5",cy:"6.5",r:".5",fill:"currentColor"}],["circle",{cx:"17.5",cy:"10.5",r:".5",fill:"currentColor"}],["circle",{cx:"6.5",cy:"12.5",r:".5",fill:"currentColor"}],["circle",{cx:"8.5",cy:"7.5",r:".5",fill:"currentColor"}]]);N("image",[["rect",{width:"18",height:"18",x:"3",y:"3",rx:"2",ry:"2"}],["circle",{cx:"9",cy:"9",r:"2"}],["path",{d:"m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"}]]);const Wr="font-['Montserrat','Inter',sans-serif] font-black",ps=({size:n=36})=>e.jsx("img",{src:B("/eos-emblem.png"),alt:"","aria-hidden":!0,className:"flex-shrink-0 object-contain",style:{width:n,height:n}}),us=({className:n="text-[19px]",inverse:t=!1})=>e.jsxs("span",{className:`${Wr} uppercase leading-none tracking-[-0.02em] whitespace-nowrap ${n}`,"aria-label":"Education OS",children:[e.jsx("span",{className:t?"text-white":"text-[#001E57]",children:"Education"})," ",e.jsx("span",{className:"bg-[linear-gradient(135deg,#FD8305_0%,#FB6406_45%,#E0073F_100%)] bg-clip-text text-transparent",children:"OS"})]}),Yr=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: digilocker
kind: integration              # feature | platform | integration
domain: integrations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "DigiLocker adapter for issuing and verifying academic certificates."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,zr=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: external-university-portals
kind: integration              # feature | platform | integration
domain: integrations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Other university and inter-institution portal adapters."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Kr=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: government-portals
kind: integration              # feature | platform | integration
domain: integrations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "UGC, AISHE, NAAC and similar government reporting portals."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Qr=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: messaging-providers
kind: integration              # feature | platform | integration
domain: integrations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Email, SMS and WhatsApp provider adapters."
owners: [himanshu-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, integration-hub]   # integration-hub owns the port this
                                                 # adapter implements and the registry it
                                                 # registers with.
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  port: contracts/port.yaml       # OutboundMessaging; what platform/notification depends on
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Jr=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: nad
kind: integration              # feature | platform | integration
domain: integrations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "National Academic Depository adapter for academic records."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Xr=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: payment-sbiepay
kind: integration              # feature | platform | integration
domain: integrations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress         # planned | in-progress | stable | deprecated
description: "SBIePay payment gateway adapter (initiate, callback, reconcile)."
owners: [gokulalakshmirooman-source]                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
# documents: settlement report uploads. scheduler: expiry sweep and daily reconciliation.
depends_on:
  platform: [identity, audit, documents, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Zr=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: video-conferencing
kind: integration              # feature | platform | integration
domain: integrations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Zoom, Teams and Webex adapters for online classes and meetings."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,eo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: wearables
kind: integration              # feature | platform | integration
domain: integrations
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Fitness and wearable device APIs for athlete data."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,no=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: academic-management
kind: feature              # feature | platform | integration
domain: academics
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Programmes, curriculum, courses, credits, faculty-course assignment."
owners: [shivanisinghrooman-09]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, event-bus]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
# Agreed with enrolment-registration on issue #100 and handled by application/roster.py; listed here once
# enrolment-registration publishes them in its events.yaml (docs/prd.md section 13):
#   enrolment-registration.course-registration.confirmed
#   enrolment-registration.course-registration.withdrawn
#   enrolment-registration.section-allocation.changed
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,to=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: examinations
kind: feature              # feature | platform | integration
domain: academics
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Exam scheduling, hall tickets, evaluation, results, transcripts."
owners: [shivanisinghrooman-09]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, event-bus, documents]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
# Pending confirmation from owners (docs/prd.md section 12): academic period, course offering and
# instructor assignment events from academic-management; course registration from
# enrolment-registration; student status from student-information; attendance from
# timetable-attendance and dues from fees-accounts if events are chosen (Q4, Q5).
# platform/workflow is not a dependency until Q10 is decided.
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,so=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: lms
kind: feature              # feature | platform | integration
domain: academics
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Learning management: content, assignments, quizzes, discussions, grading."
owners: [shivanisinghrooman-09]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, event-bus, documents]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
# Pending confirmation from owners (docs/prd.md section 12): course offering, section, academic
# period and instructor assignment events from academic-management; course offering and section
# registration from enrolment-registration. No scheduled-class events are consumed (owner decision
# C19). search, scheduler and notification are not dependencies in week 1 (LQ14).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,ao=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: timetable-attendance
kind: feature              # feature | platform | integration
domain: academics
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Timetable generation, class scheduling, attendance capture and reports."
owners: [shivanisinghrooman-09]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, event-bus]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
# Pending confirmation from owners (docs/prd.md section 11): academic period, course offering,
# section and instructor assignment events from academic-management; student-section
# allocation events from enrolment-registration. Exact names are not yet confirmed.
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,io=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: alumni
kind: feature              # feature | platform | integration
domain: campus-life
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Alumni directory, events, donations, engagement campaigns."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,ro=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: hostel
kind: feature              # feature | platform | integration
domain: campus-life
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.2.0
status: in-progress         # planned | in-progress | stable | deprecated
description: "Room allocation, mess, visitors, discipline and fee linkage."
owners: [tejaswini-rooman]              # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,oo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: library
kind: feature              # feature | platform | integration
domain: campus-life
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress         # planned | in-progress | stable | deprecated
description: "Catalogue, circulation, digital library, fines, reservations."
owners: [tejaswini-rooman]              # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler, search]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,lo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: placement-career
kind: feature              # feature | platform | integration
domain: campus-life
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Placement drives, companies, applications, offers, career services."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,co=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: transport
kind: feature              # feature | platform | integration
domain: campus-life
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress         # planned | in-progress | stable | deprecated
description: "Routes, vehicles, passes, driver management, tracking."
owners: [tejaswini-rooman]              # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,mo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: asset-management
kind: feature              # feature | platform | integration
domain: facilities
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Fixed asset register: tagging, transfers, physical verification, depreciation and disposal."
owners: [Ashritharooman]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler, documents]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,po=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: facility-booking
kind: feature              # feature | platform | integration
domain: facilities
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Generic resource-booking pattern: bookable resources, availability and bookings with optional approval. Field words come from the profile vocabulary."
owners: [Ashritharooman]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler, documents]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,uo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: inventory-equipment
kind: feature              # feature | platform | integration
domain: facilities
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Generic inventory pattern: catalogue, units, store locations, stock ledger, low stock and loans. Field words come from the profile vocabulary."
owners: [Ashritharooman]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler, documents]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,go=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: maintenance
kind: feature              # feature | platform | integration
domain: facilities
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Fault tickets and work orders for assets, spaces and equipment: assignment to technicians or vendors, SLA, work log and preventive schedules."
owners: [Ashritharooman]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler, documents]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,ho=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: sports-facilities
kind: feature              # feature | platform | integration
domain: facilities
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Registry of grounds, courts, pools, gyms and their usage."
owners: [akshatatrathodrooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,fo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: budget-grants
kind: feature              # feature | platform | integration
domain: finance-operations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress         # planned | in-progress | stable | deprecated
description: "Budget planning, grant tracking, utilisation certificates."
owners: [gokulalakshmirooman-source]                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
# documents: sanction orders, vouchers, certificate PDFs. notification: thresholds and certificates due. scheduler: due reminders.
depends_on:
  platform: [identity, audit, documents, notification, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
# Spend from other modules. These events are proposed in the hr-payroll and procurement contracts (issue #66).
consumes_events:
  - hr-payroll.payroll-run.paid
  - procurement.purchase-order.issued
  - procurement.purchase-order.cancelled
  - procurement.vendor-invoice.paid

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,yo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: e-office
kind: feature              # feature | platform | integration
domain: finance-operations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "File movement, notings, approvals, digital correspondence."
owners: [gokulalakshmirooman-source]                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
# documents: attachments and scanned correspondence. notification: file movement. scheduler: overdue files.
depends_on:
  platform: [identity, audit, documents, notification, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,bo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: fees-accounts
kind: feature              # feature | platform | integration
domain: finance-operations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress         # planned | in-progress | stable | deprecated
description: "Fee structures, invoices, online payments, receipts, ledgers."
owners: [gokulalakshmirooman-source]                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
# documents: receipt PDFs and concession proofs. notification: dues and receipts. scheduler: overdue sweep, late fees.
depends_on:
  platform: [identity, audit, documents, notification, scheduler]
  integrations: [payment-sbiepay]

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events:
  - payment-sbiepay.payment.succeeded
  - payment-sbiepay.payment.failed
  - payment-sbiepay.payment.refunded
  # Raises the admission (confirmation) fee invoice. Needs a person id in the payload; asked on #192.
  - admissions.application.accepted
  # Agreed with hostel, transport and library on #175: raise and cancel their fee invoices.
  - hostel.allocation.confirmed
  - hostel.allocation.cancelled
  - transport.pass.issued
  - transport.pass.cancelled
  - library.fine.raised
  - library.fine.waived

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,xo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: hr-payroll
kind: feature              # feature | platform | integration
domain: finance-operations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Employee master, leave, payroll, appraisals, service records."
owners: [gokulalakshmirooman-source]                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
# documents: payslip PDFs and service orders. notification: leave and payslip notices. scheduler: exits on the last working day.
depends_on:
  platform: [identity, audit, documents, notification, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,vo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: procurement
kind: feature              # feature | platform | integration
domain: finance-operations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Indents, tenders, purchase orders, vendor management."
owners: [gokulalakshmirooman-source]                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
# documents: specifications, quotes, order PDFs, bills. notification: approvals and orders to vendors.
# Also calls the budget-grants contract (GET /lines, GET /availability) through the gateway (ADR-0003).
depends_on:
  platform: [identity, audit, documents, notification]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,wo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: grievance
kind: feature              # feature | platform | integration
domain: governance
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "SGRC, anti-ragging and POSH-ICC complaint intake and resolution."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []        # none

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,ko=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: iqac-accreditation
kind: feature              # feature | platform | integration
domain: governance
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "IQAC data collection, NAAC/NBA metrics, evidence repository."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []        # none

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,_o=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: regulatory-reports
kind: feature              # feature | platform | integration
domain: governance
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "UGC, AISHE, NIRF and other statutory reporting."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []        # none in v1; see docs/prd.md open question 2

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,jo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: rti
kind: feature              # feature | platform | integration
domain: governance
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "RTI request intake, assignment, tracking and responses."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []        # none

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Fo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: field-training
kind: feature              # feature | platform | integration
domain: practice
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress         # planned | in-progress | stable | deprecated
description: "Field training placements: clinical rotations, teaching practice, farm rotations, internships, court visits."
owners: [tejaswini-rooman]              # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,No=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: portfolio
kind: feature              # feature | platform | integration
domain: practice
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Learner portfolios: artworks, repertoire, showreels, designs, teaching and research portfolios."
owners: [praveen-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,So=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: productions
kind: feature              # feature | platform | integration
domain: practice
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Productions and events: performances, exhibitions, recitals, screenings, hackathons, competitions, conferences."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Eo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: projects
kind: feature              # feature | platform | integration
domain: practice
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress         # planned | in-progress | stable | deprecated
description: "Projects with milestones, teams and reviews: capstone, film, live business, research, artwork."
owners: [tejaswini-rooman]              # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler, documents]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Ao=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: selection-process
kind: feature              # feature | platform | integration
domain: practice
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Auditions, casting, squad selection, jury rounds, moot court teams, supervisor allocation."
owners: [praveen-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Co=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: skill-progress
kind: feature              # feature | platform | integration
domain: practice
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Skill assessments and progression over time: technique, fitness, practicum, competencies."
owners: [akshatatrathodrooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Po=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: athlete-performance
kind: feature              # feature | platform | integration
domain: sports
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Athlete profiles, performance metrics, fitness testing, benchmarks."
owners: [akshatatrathodrooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Ro=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: sports-nutrition-health
kind: feature              # feature | platform | integration
domain: sports
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: in-progress           # planned | in-progress | stable | deprecated
description: "Diet plans, medical records, injury tracking, physio sessions."
owners: [akshatatrathodrooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: [athlete-performance.athlete.registered]

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Mo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: tournament-events
kind: feature              # feature | platform | integration
domain: sports
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Tournaments, fixtures, results, officials and event logistics."
owners: [akshatatrathodrooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: [athlete-performance.athlete.registered, athlete-performance.athlete.updated]

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Do=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: training-video-analysis
kind: feature              # feature | platform | integration
domain: sports
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Training plans, sessions, video upload, tagging and annotation."
owners: [akshatatrathodrooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: [athlete-performance.athlete.registered, athlete-performance.athlete.updated]

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Oo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: admissions
kind: feature              # feature | platform | integration
domain: student-lifecycle
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Online application, document verification, merit lists, counselling and offers."
owners: [praveen-rooman]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,To=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: enrolment-registration
kind: feature              # feature | platform | integration
domain: student-lifecycle
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Programme enrolment with roll numbers, term registration windows, course registration and section allocation."
owners: [praveen-rooman]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events:
  - academic-management.term.created
  - academic-management.term.activated
  - academic-management.offering.created
  - academic-management.offering.updated
  - academic-management.offering.status-changed
  - academic-management.section.created
  - academic-management.section.updated

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Bo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: student-information
kind: feature              # feature | platform | integration
domain: student-lifecycle
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Student master record (SIS): profiles, documents, ID cards, status history."
owners: [praveen-rooman]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Lo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: web-portal-cms
kind: feature              # feature | platform | integration
domain: student-lifecycle
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Public website, CMS pages, announcements, news and notices."
owners: [praveen-rooman]  # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Io=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: amc-vendor-support
kind: feature              # feature | platform | integration
domain: support
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "AMC contracts, vendor support engagements, renewals."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []        # none in v1; procurement.vendor.blacklisted is docs/prd.md open question 2

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,qo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: helpdesk
kind: feature              # feature | platform | integration
domain: support
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.2.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Ticketing for all user roles with categories and routing."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, documents, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []        # none in v1; see docs/prd.md open questions 2 and 6

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,$o=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: incident-management
kind: feature              # feature | platform | integration
domain: support
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Incident and problem records, root cause analysis."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, documents]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []        # none in v1; see docs/prd.md open question 3

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Vo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: knowledge-base
kind: feature              # feature | platform | integration
domain: support
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Articles, FAQs and how-to guides for self-service."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification]   # search and documents: docs/prd.md open questions 1 and 2
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []        # none in v1

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Ho=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: sla-management
kind: feature              # feature | platform | integration
domain: support
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "SLA definitions, timers, escalation and breach tracking."
owners: [madhumitha-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, scheduler]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events:            # helpdesk contracts/events.yaml; timer delivery from scheduler is docs/prd.md open question 1
  - helpdesk.ticket.created
  - helpdesk.ticket.assigned
  - helpdesk.ticket.responded
  - helpdesk.ticket.status-changed
  - helpdesk.ticket.reclassified
  - helpdesk.ticket.resolved
  - helpdesk.ticket.reopened
  - helpdesk.ticket.closed
  - helpdesk.ticket.cancelled

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Uo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: api-gateway
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Edge routing, auth enforcement, rate limiting, request logging and monitoring."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Go=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: audit
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Immutable, append-only audit log for every state-changing action."
owners: [himanshu-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity]           # permission checks and resolving an actor's name.
                                 # Deliberately NOT audit itself, and NOT event-bus: audit must
                                 # stay writable when everything else is down.
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Wo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: billing
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Plans, trials, subscriptions, upgrades and invoices."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

depends_on:
  platform: [identity, audit, notification, scheduler, documents]
  integrations: [payment-sbiepay]

exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

consumes_events:
  - tenancy.organisation.registered
  - tenancy.organisation.archived

config: config/env.example
portable: false
`,Yo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: documents
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Document and media management: storage abstraction, versioning, access control."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,zo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: event-bus
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Domain event contracts and broker abstraction. The only async channel between modules."
owners: [himanshu-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]   # identity: permission checks on the ops API.
                                # audit: a replay is an operator action and is recorded.
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Ko=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: identity
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "SSO (SAML / OAuth2 / OIDC), RBAC with fine-grained permissions, MFA, session management."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Qo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: integration-hub
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Adapter registry, data exchange (XML / JSON / CSV), webhooks, retries."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Jo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: notification
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Email, SMS, WhatsApp, push and in-app notifications with templates."
owners: [himanshu-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, event-bus, documents, scheduler]
  integrations: [messaging-providers]   # the physical transport; this module never talks to
                                        # a provider directly.

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events:
  - tenancy.organisation.registered
  - tenancy.organisation.verified
  - tenancy.organisation.approved
  - tenancy.package.requested
  - tenancy.package.changed
  - identity.user.created
  - billing.subscription.started
  - billing.trial.expired
  - billing.subscription.upgraded

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Xo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: reporting
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Dashboards, MIS reports, analytics and warehouse ETL."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Zo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: scheduler
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: in-progress       # planned | in-progress | stable | deprecated
description: "Jobs, cron, reminders and alert dispatch."
owners: [himanshu-rooman] # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, event-bus]   # event-bus is how a due job reaches the module
                                           # that owns it; scheduler cannot import it.
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,el=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: search
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Global search indexing and query (Elasticsearch-class engine)."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,nl=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: tenancy
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Organisations (tenants), self-service registration, academy type, entitlements."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit, notification, billing]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events:
  - billing.subscription.started
  - billing.subscription.upgraded
  - billing.subscription.expired
  - billing.trial.expired

config: config/env.example
portable: false
`,tl=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: workflow
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Configurable workflow and approval engine (state machines, SLAs, delegation)."
owners: []                # GitHub handles. Keep in sync with CODEOWNERS.

# Platform services this module calls through packages/sdk. Nothing else.
depends_on:
  platform: [identity, audit]
  integrations: []

# Public surface. Other modules may ONLY use these.
exposes:
  api: contracts/openapi.yaml
  events: contracts/events.yaml
  permissions: contracts/permissions.yaml

# Events this module subscribes to (by name, from other modules' events.yaml).
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,sl=`# Permission catalogue for messaging-providers. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
#
# Provider credentials are platform-level, so configuring them is a super-admin act. An
# organisation admin never touches providers; they manage templates in platform/notification.
module: messaging-providers
permissions:
  - key: messaging-providers:provider:read
    description: >-
      View which providers are configured and whether they are reachable. Never returns
      credentials, masked or otherwise.
  - key: platform:messaging-providers:admin
    description: >-
      Super admin only. Enable or disable a provider and send a test message. Credentials
      themselves arrive as environment variables and are not editable through the API.

# Blocks are named with platform role ids, the roles a token carries. No profile gives a person a
# provider-support role, so only the super admin holds these keys; no organisation role holds either.
roles:
  # A super admin is handed only the platform: keys that some role grants (eos_core.config.permissions_for), so
  # without this the admin key would be held by nobody. Same pattern as platform/billing's super-admin role.
  - name: super-admin
    description: >-
      Super admin: sees which providers are configured and reachable, and sends a test message.
    grants:
      - messaging-providers:provider:read
      - platform:messaging-providers:admin
`,al=`# Permission catalogue for payment-sbiepay. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: payment-sbiepay
permissions:
  - key: payment-sbiepay:payment:initiate
    description: Start a payment for oneself or one's organisation (fee or plan upgrade).
  - key: payment-sbiepay:payment:read
    description: View the organisation's payments, reconciliation summary and runs.
  - key: payment-sbiepay:payment:refund
    description: Refund all or part of a successful payment.
  - key: payment-sbiepay:payment:reconcile
    description: Re-verify pending payments and run settlement reconciliation.
  - key: payment-sbiepay:merchant-account:manage
    description: View and set the organisation's SBIePay merchant account.
roles:
  - name: applicant
    grants: [payment-sbiepay:payment:initiate]
  - name: student
    grants: [payment-sbiepay:payment:initiate]
  - name: finance-staff
    grants: [payment-sbiepay:payment:read, payment-sbiepay:payment:refund, payment-sbiepay:payment:reconcile]
  - name: org-admin
    grants: [payment-sbiepay:payment:initiate, payment-sbiepay:payment:read, payment-sbiepay:merchant-account:manage]
`,il=`# Permission catalogue for academic-management. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Role blocks are platform role ids (platform/identity/config/profiles); eos_core.permissions_for
# grants a user the keys of every block named after one of their roles.
module: academic-management
permissions:
  - key: academic-management:term:read
    description: View academic terms
  - key: academic-management:term:write
    description: Create and edit terms; activate a term
  - key: academic-management:programme:read
    description: View programmes
  - key: academic-management:programme:write
    description: Create, edit and archive programmes
  - key: academic-management:curriculum:read
    description: View curricula and their versions
  - key: academic-management:curriculum:write
    description: Create and edit draft curricula
  - key: academic-management:curriculum:publish
    description: Publish a curriculum version
  - key: academic-management:course:read
    description: View the course catalogue
  - key: academic-management:course:write
    description: Create, edit and archive courses
  - key: academic-management:offering:read
    description: View course offerings and sections
  - key: academic-management:offering:write
    description: Create and edit offerings and sections; change offering status
  - key: academic-management:faculty-assignment:read
    description: View faculty assignments
  - key: academic-management:faculty-assignment:write
    description: Assign faculty to offerings and sections; end assignments
  - key: academic-management:roster:read
    description: View rosters of offerings the user is assigned to
  - key: academic-management:roster:read-all
    description: View rosters of every offering in the organisation or the user's department
  - key: academic-management:faculty-load:read
    description: View faculty teaching load per term
roles:
  - name: org-admin
    description: Full administration of the academic catalogue.
    grants:
      - academic-management:term:read
      - academic-management:term:write
      - academic-management:programme:read
      - academic-management:programme:write
      - academic-management:curriculum:read
      - academic-management:curriculum:write
      - academic-management:curriculum:publish
      - academic-management:course:read
      - academic-management:course:write
      - academic-management:offering:read
      - academic-management:offering:write
      - academic-management:faculty-assignment:read
      - academic-management:faculty-assignment:write
      - academic-management:roster:read-all
      - academic-management:faculty-load:read
  - name: department-admin
    description: Plans offerings and faculty for a department (HoD).
    grants:
      - academic-management:term:read
      - academic-management:programme:read
      - academic-management:curriculum:read
      - academic-management:curriculum:write
      - academic-management:course:read
      - academic-management:course:write
      - academic-management:offering:read
      - academic-management:offering:write
      - academic-management:faculty-assignment:read
      - academic-management:faculty-assignment:write
      - academic-management:roster:read-all
      - academic-management:faculty-load:read
  - name: faculty
    description: Teaches offerings and reads their rosters.
    grants:
      - academic-management:term:read
      - academic-management:programme:read
      - academic-management:curriculum:read
      - academic-management:course:read
      - academic-management:offering:read
      - academic-management:faculty-assignment:read
      - academic-management:roster:read
  - name: student
    description: Read-only view of the catalogue.
    grants:
      - academic-management:term:read
      - academic-management:programme:read
      - academic-management:curriculum:read
      - academic-management:course:read
      - academic-management:offering:read
  - name: examination-staff
    description: Read-only view of the catalogue, to plan exams.
    grants:
      - academic-management:term:read
      - academic-management:programme:read
      - academic-management:curriculum:read
      - academic-management:course:read
      - academic-management:offering:read
`,rl=`# Permission catalogue for examinations. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
#
# Scope rules (docs/prd.md section 13). Modules check keys, never roles. Each scope is its own key,
# and a key always means the same scope whoever holds it:
# - *-assigned: papers or sessions the caller holds an exam duty for.
# - *-department: the caller's department, as recorded on the course offering. How the caller's
#   department is obtained from platform/identity is pending confirmation (docs/prd.md Q13).
# - *-all: the whole organisation.
# - *-own: the caller's own data (student: own candidacy, hall ticket, published results;
#   staff: own duties).
# An operation's x-permission is its narrowest key; holding a wider key of the same action widens the
# scope, and the widest key held applies. Roles therefore hold the narrowest key plus any wider ones.
module: examinations
permissions:
  - key: examinations:exam-cycle:read
    description: View exam cycles
  - key: examinations:exam-cycle:manage
    description: Create, configure and change the status of exam cycles
  - key: examinations:assessment-scheme:read
    description: View assessment schemes
  - key: examinations:assessment-scheme:write-department
    description: Define and activate assessment schemes for course offerings of the caller's department
  - key: examinations:assessment-scheme:write-all
    description: Define and activate assessment schemes for any course offering
  - key: examinations:grading-scheme:read
    description: View grading schemes
  - key: examinations:grading-scheme:manage
    description: Define grading schemes and set the organisation default
  - key: examinations:paper:read
    description: View exam papers
  - key: examinations:paper:manage
    description: Create and edit exam papers
  - key: examinations:session:read
    description: View exam sessions
  - key: examinations:session:read-own
    description: View the exam sessions the caller is a candidate in
  - key: examinations:session:manage
    description: Schedule, reschedule and cancel exam sessions
  - key: examinations:candidate:read-department
    description: View candidates and eligibility for papers of the caller's department
  - key: examinations:candidate:read-all
    description: View candidates and eligibility for any paper
  - key: examinations:candidate:determine
    description: Run eligibility determination for an exam cycle
  - key: examinations:candidate:override
    description: Override a candidate's eligibility, with a reason
  - key: examinations:hall-ticket:read-own
    description: View the caller's own hall ticket
  - key: examinations:hall-ticket:read-all
    description: View any hall ticket and hall-ticket reports
  - key: examinations:hall-ticket:issue
    description: Issue hall tickets
  - key: examinations:hall-ticket:withhold
    description: Withhold a hall ticket, with a reason
  - key: examinations:hall-ticket:revoke
    description: Revoke a hall ticket, with a reason
  - key: examinations:duty:read-own
    description: View the caller's own exam duties
  - key: examinations:duty:read-department
    description: View exam duties for papers and sessions of the caller's department
  - key: examinations:duty:read-all
    description: View any exam duty
  - key: examinations:duty:assign
    description: Assign and cancel exam duties
  - key: examinations:marks:read-assigned
    description: View marks of papers the caller evaluates or moderates
  - key: examinations:marks:read-department
    description: View marks of papers of the caller's department
  - key: examinations:marks:read-all
    description: View marks of any paper
  - key: examinations:marks:enter-assigned
    description: Enter marks for papers the caller holds an evaluation duty for
  - key: examinations:marks:enter-all
    description: Enter or correct marks for any paper before it is locked
  - key: examinations:marks:moderate-assigned
    description: Moderate papers the caller holds a moderation duty for, with a reason
  - key: examinations:marks:moderate-department
    description: Moderate papers of the caller's department, with a reason
  - key: examinations:marks:lock
    description: Lock a paper's marks after moderation
  - key: examinations:result:read-own
    description: View the caller's own published results
  - key: examinations:result:read-department
    description: View results for course offerings of the caller's department
  - key: examinations:result:read-all
    description: View any result
  - key: examinations:result:compute
    description: Compute results from locked marks
  - key: examinations:result:approve-department
    description: Approve computed results for course offerings of the caller's department
  - key: examinations:result:approve-all
    description: Approve computed results for any course offering
  - key: examinations:result:publish
    description: Publish approved results
  - key: examinations:result:revise
    description: Revise a published result, with a reason
  - key: examinations:report:read-department
    description: View examination reports for the caller's department
  - key: examinations:report:read-all
    description: View examination reports for the organisation
roles:
  - name: examinations-controller
    description: Runs examinations for the organisation. Default for examination-staff and org-admin.
    grants:
      - examinations:exam-cycle:read
      - examinations:exam-cycle:manage
      - examinations:assessment-scheme:read
      - examinations:assessment-scheme:write-department
      - examinations:assessment-scheme:write-all
      - examinations:grading-scheme:read
      - examinations:grading-scheme:manage
      - examinations:paper:read
      - examinations:paper:manage
      - examinations:session:read
      - examinations:session:manage
      - examinations:candidate:read-all
      - examinations:candidate:read-department
      - examinations:candidate:determine
      - examinations:candidate:override
      - examinations:hall-ticket:read-all
      - examinations:hall-ticket:issue
      - examinations:hall-ticket:withhold
      - examinations:hall-ticket:revoke
      - examinations:duty:read-all
      - examinations:duty:read-department
      - examinations:duty:assign
      - examinations:marks:read-all
      - examinations:marks:read-assigned
      - examinations:marks:enter-assigned
      - examinations:marks:enter-all
      - examinations:marks:lock
      - examinations:result:read-all
      - examinations:result:read-department
      - examinations:result:compute
      - examinations:result:approve-all
      - examinations:result:approve-department
      - examinations:result:publish
      - examinations:result:revise
      - examinations:report:read-all
      - examinations:report:read-department
  - name: examinations-department-head
    description: Sets assessment schemes, moderates and approves results for a department. Default for department-admin.
    grants:
      - examinations:exam-cycle:read
      - examinations:assessment-scheme:read
      - examinations:assessment-scheme:write-department
      - examinations:grading-scheme:read
      - examinations:paper:read
      - examinations:session:read
      - examinations:candidate:read-department
      - examinations:duty:read-department
      - examinations:marks:read-department
      - examinations:marks:read-assigned
      - examinations:marks:moderate-department
      - examinations:marks:moderate-assigned
      - examinations:result:read-department
      - examinations:result:approve-department
      - examinations:report:read-department
  - name: examinations-faculty
    description: Invigilates, evaluates and moderates as assigned. Default for faculty.
    grants:
      - examinations:exam-cycle:read
      - examinations:assessment-scheme:read
      - examinations:paper:read
      - examinations:session:read
      - examinations:duty:read-own
      - examinations:marks:read-assigned
      - examinations:marks:enter-assigned
      - examinations:marks:moderate-assigned
  - name: examinations-student
    description: Sits exams and sees their own hall ticket and published results. Default for student.
    grants:
      - examinations:session:read-own
      - examinations:hall-ticket:read-own
      - examinations:result:read-own
  - name: examinations-viewer
    description: Read-only access to exam setup and organisation-wide reports.
    grants:
      - examinations:exam-cycle:read
      - examinations:assessment-scheme:read
      - examinations:grading-scheme:read
      - examinations:paper:read
      - examinations:session:read
      - examinations:report:read-department
      - examinations:report:read-all
`,ol=`# Permission catalogue for lms. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
#
# Scope rules (docs/prd.md section 13). Modules check keys, never roles. Each scope is its own key,
# and a key always means the same scope whoever holds it:
# - *-own: the caller's own records (submissions, attempts, released grades), and the course spaces
#   the caller belongs to as student or instructor.
# - *-assigned: course spaces the caller teaches (instructor assignment, docs/prd.md LQ5; no
#   teaching-assistant role in Week 1, owner decision C18).
# - *-department: course spaces of the caller's department. How the caller's department is obtained
#   from platform/identity is pending confirmation (docs/prd.md LQ13).
# - *-all: every course space in the organisation.
# An operation's x-permission is its narrowest key; holding a wider key of the same action widens the
# scope, and the widest key held applies. Roles therefore hold the narrowest key plus any wider ones.
module: lms
permissions:
  - key: lms:course-space:read-own
    description: View the course spaces the caller belongs to and their published content
  - key: lms:course-space:read-department
    description: View the course spaces of the caller's department and their published content
  - key: lms:course-space:read-all
    description: View every course space and its published content
  - key: lms:course-space:manage-assigned
    description: Edit settings, activate and archive the course spaces the caller teaches
  - key: lms:course-space:manage-all
    description: Create course spaces and edit, activate or archive any course space
  - key: lms:material:manage-assigned
    description: Create, edit, publish and unpublish content units and materials in course spaces the caller teaches
  - key: lms:material:manage-all
    description: Manage content units and materials in any course space
  - key: lms:assignment:manage-assigned
    description: Create, edit, publish and close assignments in course spaces the caller teaches
  - key: lms:assignment:manage-all
    description: Manage assignments in any course space
  - key: lms:quiz:manage-assigned
    description: Create, edit, publish and close quizzes in course spaces the caller teaches, including answer keys
  - key: lms:quiz:manage-all
    description: Manage quizzes in any course space
  - key: lms:submission:submit-own
    description: Submit to assignments in the caller's own course spaces
  - key: lms:submission:read-own
    description: View the caller's own submissions
  - key: lms:submission:read-assigned
    description: View submissions in course spaces the caller teaches
  - key: lms:submission:read-all
    description: View submissions in any course space
  - key: lms:quiz-attempt:attempt-own
    description: Start, answer and submit quiz attempts in the caller's own course spaces
  - key: lms:quiz-attempt:read-own
    description: View the caller's own quiz attempts
  - key: lms:quiz-attempt:read-assigned
    description: View quiz attempts in course spaces the caller teaches
  - key: lms:quiz-attempt:read-all
    description: View quiz attempts in any course space
  - key: lms:grade:read-own
    description: View the caller's own released coursework grades
  - key: lms:grade:read-assigned
    description: View gradebooks, including draft grades, of course spaces the caller teaches
  - key: lms:grade:read-department
    description: View gradebooks of course spaces in the caller's department
  - key: lms:grade:read-all
    description: View gradebooks of any course space
  - key: lms:grade:manage-assigned
    description: Grade, give feedback, score essay questions and release grades in course spaces the caller teaches
  - key: lms:grade:manage-all
    description: Grade and release grades in any course space
  - key: lms:discussion:post-own
    description: Start threads and post replies in the caller's own course spaces
  - key: lms:discussion:moderate-assigned
    description: Lock, unlock, hide and unhide threads and posts in course spaces the caller teaches
  - key: lms:discussion:moderate-all
    description: Moderate discussions in any course space
  - key: lms:report:read-department
    description: View coursework activity reports for the caller's department
  - key: lms:report:read-all
    description: View coursework activity reports for the organisation
roles:
  - name: lms-admin
    description: Administers lms for the organisation. Default for org-admin.
    grants:
      - lms:course-space:read-own
      - lms:course-space:read-all
      - lms:course-space:manage-assigned
      - lms:course-space:manage-all
      - lms:material:manage-assigned
      - lms:material:manage-all
      - lms:assignment:manage-assigned
      - lms:assignment:manage-all
      - lms:quiz:manage-assigned
      - lms:quiz:manage-all
      - lms:submission:read-assigned
      - lms:submission:read-all
      - lms:quiz-attempt:read-assigned
      - lms:quiz-attempt:read-all
      - lms:grade:read-assigned
      - lms:grade:read-all
      - lms:grade:manage-assigned
      - lms:grade:manage-all
      - lms:discussion:post-own
      - lms:discussion:moderate-assigned
      - lms:discussion:moderate-all
      - lms:report:read-department
      - lms:report:read-all
  - name: lms-department-head
    description: Oversees coursework in the department. Default for department-admin.
    grants:
      - lms:course-space:read-own
      - lms:course-space:read-department
      - lms:grade:read-assigned
      - lms:grade:read-department
      - lms:report:read-department
  - name: lms-instructor
    description: Teaches in course spaces. Default for faculty. No teaching-assistant role in Week 1 (owner decision C18).
    grants:
      - lms:course-space:read-own
      - lms:course-space:manage-assigned
      - lms:material:manage-assigned
      - lms:assignment:manage-assigned
      - lms:quiz:manage-assigned
      - lms:submission:read-assigned
      - lms:quiz-attempt:read-assigned
      - lms:grade:read-assigned
      - lms:grade:manage-assigned
      - lms:discussion:post-own
      - lms:discussion:moderate-assigned
  - name: lms-student
    description: Learns in the course spaces they belong to. Default for student.
    grants:
      - lms:course-space:read-own
      - lms:submission:submit-own
      - lms:submission:read-own
      - lms:quiz-attempt:attempt-own
      - lms:quiz-attempt:read-own
      - lms:grade:read-own
      - lms:discussion:post-own
  - name: lms-viewer
    description: Read-only access to course spaces and organisation-wide reports.
    grants:
      - lms:course-space:read-own
      - lms:course-space:read-all
      - lms:report:read-department
      - lms:report:read-all
`,ll=`# Permission catalogue for timetable-attendance. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
#
# Scope rules (docs/prd.md section 12). Modules check keys, never roles, so scope is widened only
# by holding a further key:
# - attendance-session:open|close and attendance-record:mark|correct apply to classes the caller
#   teaches. attendance-record:correct-department widens correct to the caller's department;
#   attendance-session:override widens all four to the organisation.
# - attendance-session:read and attendance-record:read return classes the caller teaches,
#   widened to the department by report:read-department and to the organisation by report:read-all.
# - *:read-own returns only the caller's own data.
# - How the caller's department is known, and whether timetable and scheduled-class writes are
#   limited to it, is pending confirmation from platform/identity (docs/prd.md Q9).
module: timetable-attendance
permissions:
  - key: timetable-attendance:timetable:read
    description: View timetables and their slots
  - key: timetable-attendance:timetable:write
    description: Create timetables and edit draft or unpublished timetables
  - key: timetable-attendance:timetable:publish
    description: Publish or unpublish a timetable
  - key: timetable-attendance:scheduled-class:read
    description: View scheduled classes
  - key: timetable-attendance:scheduled-class:read-own
    description: View the scheduled classes of the caller's own sections
  - key: timetable-attendance:scheduled-class:write
    description: Generate scheduled classes, create ad-hoc classes, reschedule classes
  - key: timetable-attendance:scheduled-class:cancel
    description: Cancel a scheduled class
  - key: timetable-attendance:attendance-session:read
    description: View attendance sessions
  - key: timetable-attendance:attendance-session:open
    description: Open the attendance session for a class the caller teaches
  - key: timetable-attendance:attendance-session:close
    description: Close the attendance session for a class the caller teaches
  - key: timetable-attendance:attendance-session:override
    description: Open, close, mark and correct attendance for any class, outside own-class and time-window limits
  - key: timetable-attendance:attendance-record:read
    description: View attendance records
  - key: timetable-attendance:attendance-record:read-own
    description: View the caller's own attendance records
  - key: timetable-attendance:attendance-record:mark
    description: Mark attendance in an open session for a class the caller teaches
  - key: timetable-attendance:attendance-record:correct
    description: Correct a record in a closed session, with a reason, within the correction window
  - key: timetable-attendance:attendance-record:correct-department
    description: Widens correct to every class in the caller's department, after the correction window too
  - key: timetable-attendance:report:read-own
    description: View the caller's own attendance summary and history
  - key: timetable-attendance:report:read-department
    description: View attendance reports for the caller's department
  - key: timetable-attendance:report:read-all
    description: View attendance reports for any student or department in the organisation
  - key: timetable-attendance:report:read-eligibility
    description: Read attendance counts in bulk for exam eligibility, for any course offering in the organisation (FR-18)
roles:
  - name: timetable-attendance-admin
    description: Academic or timetable administrator. Default for org-admin.
    grants:
      - timetable-attendance:timetable:read
      - timetable-attendance:timetable:write
      - timetable-attendance:timetable:publish
      - timetable-attendance:scheduled-class:read
      - timetable-attendance:scheduled-class:write
      - timetable-attendance:scheduled-class:cancel
      - timetable-attendance:attendance-session:read
      - timetable-attendance:attendance-session:open
      - timetable-attendance:attendance-session:close
      - timetable-attendance:attendance-session:override
      - timetable-attendance:attendance-record:read
      - timetable-attendance:attendance-record:mark
      - timetable-attendance:attendance-record:correct
      - timetable-attendance:report:read-department
      - timetable-attendance:report:read-all
      - timetable-attendance:report:read-eligibility
  - name: timetable-attendance-department-head
    description: Plans the department timetable and oversees its attendance. Default for department-admin.
    grants:
      - timetable-attendance:timetable:read
      - timetable-attendance:timetable:write
      - timetable-attendance:timetable:publish
      - timetable-attendance:scheduled-class:read
      - timetable-attendance:scheduled-class:write
      - timetable-attendance:scheduled-class:cancel
      - timetable-attendance:attendance-session:read
      - timetable-attendance:attendance-record:read
      - timetable-attendance:attendance-record:correct
      - timetable-attendance:attendance-record:correct-department
      - timetable-attendance:report:read-department
  - name: timetable-attendance-faculty
    description: Teaches classes and takes attendance for them. Default for faculty.
    grants:
      - timetable-attendance:timetable:read
      - timetable-attendance:scheduled-class:read
      - timetable-attendance:attendance-session:read
      - timetable-attendance:attendance-session:open
      - timetable-attendance:attendance-session:close
      - timetable-attendance:attendance-record:read
      - timetable-attendance:attendance-record:mark
      - timetable-attendance:attendance-record:correct
  - name: timetable-attendance-student
    description: Sees their own schedule and attendance. Default for student.
    grants:
      - timetable-attendance:scheduled-class:read-own
      - timetable-attendance:attendance-record:read-own
      - timetable-attendance:report:read-own
  - name: timetable-attendance-viewer
    description: Read-only access to timetables, classes, attendance and organisation-wide reports.
    grants:
      - timetable-attendance:timetable:read
      - timetable-attendance:scheduled-class:read
      - timetable-attendance:attendance-session:read
      - timetable-attendance:attendance-record:read
      - timetable-attendance:report:read-department
      - timetable-attendance:report:read-all
  - name: timetable-attendance-exam-eligibility
    description: Reads attendance counts for exam eligibility. Default for examination-staff (owner decision C7).
    grants:
      - timetable-attendance:report:read-eligibility
`,dl=`# Permission catalogue for alumni. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: alumni
permissions: []
#  - key: alumni:record:read
#    description: ...
#  - key: alumni:record:write
#    description: ...
roles: []
#  - name: alumni-admin
#    grants: [alumni:record:read, alumni:record:write]
`,cl=`# Permission catalogue for hostel. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: hostel
permissions:
  - key: hostel:hostel:read
    description: View hostels, rooms, occupancy and the mess menu.
  - key: hostel:hostel:manage
    description: Create and update hostels and rooms; close and reopen rooms.
  - key: hostel:allocation:read
    description: View room requests and allocations.
  - key: hostel:allocation:manage
    description: Allocate beds, check residents in and out, cancel allocations.
  - key: hostel:mess:manage
    description: Set the mess menu.
  - key: hostel:leave:approve
    description: View leave requests, approve or reject them, mark returns.
  - key: hostel:gate:record
    description: See approved gate passes and record a resident leaving and returning through the gate.
  - key: hostel:visitor:read
    description: View the visitor log.
  - key: hostel:visitor:record
    description: Record visitors in and out.
  - key: hostel:incident:read
    description: View discipline incidents. Restricted personal data.
  - key: hostel:incident:manage
    description: Record, update and close discipline incidents.
  - key: hostel:notice:publish
    description: Publish and withdraw hostel notices.
  - key: hostel:self:read
    description: View own allocation, notices, mess menu, leave and visitors.
  - key: hostel:self:request
    description: Request a room, apply for and withdraw own leave, cancel own room request.
roles:
  - name: hostel-admin
    description: Hostel office. Sets up hostels and rooms and runs allocation.
    grants:
      - hostel:hostel:read
      - hostel:hostel:manage
      - hostel:allocation:read
      - hostel:allocation:manage
      - hostel:mess:manage
      - hostel:leave:approve
      - hostel:visitor:read
      - hostel:incident:read
      - hostel:incident:manage
      - hostel:notice:publish
  - name: hostel-warden
    description: Warden of one or more hostels. Day-to-day residents, leave, discipline and notices.
    grants:
      - hostel:hostel:read
      - hostel:allocation:read
      - hostel:allocation:manage
      - hostel:leave:approve
      - hostel:gate:record
      - hostel:visitor:read
      - hostel:visitor:record
      - hostel:incident:read
      - hostel:incident:manage
      - hostel:notice:publish
  - name: hostel-security
    description: Security desk. Records visitors and residents leaving and returning on a gate pass.
    grants:
      - hostel:hostel:read
      - hostel:gate:record
      - hostel:visitor:read
      - hostel:visitor:record
  - name: hostel-resident
    description: Residents who do not hold the student role, for example staff living in. Students get the same grants through the student role below.
    grants:
      - hostel:self:read
      - hostel:self:request
  # Profile role (platform/identity/config/profiles). Granted directly, as fees-accounts does, so a student
  # needs no hostel-specific role. Self-service only: every endpoint behind these keys is limited to the caller.
  - name: student
    description: Every student. Own allocation, notices, mess menu, leave and gate passes, visitors; request a room and apply for leave.
    grants:
      - hostel:self:read
      - hostel:self:request
  - name: hostel-viewer
    description: Management and org admin oversight, read only. No incident access.
    grants:
      - hostel:hostel:read
      - hostel:allocation:read
`,ml=`# Permission catalogue for library. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: library
permissions:
  - key: library:catalogue:read
    description: Search titles, copies and digital resources; view loan policies.
  - key: library:catalogue:manage
    description: Catalogue titles and copies, withdraw copies, manage digital resources.
  - key: library:member:manage
    description: Add, view, recategorise, block and unblock members.
  - key: library:policy:manage
    description: Set loan policies per member category.
  - key: library:circulation:manage
    description: Issue, return, renew and mark loans lost; view and cancel reservations.
  - key: library:fine:manage
    description: View fines, record payment and waive fines.
  - key: library:self:read
    description: Search the catalogue and digital resources; view own loans, reservations and fines.
  - key: library:self:borrow
    description: Renew own loans, reserve titles and cancel own reservations.
roles:
  - name: library-admin
    description: Head librarian. Everything, including loan policies.
    grants:
      - library:catalogue:read
      - library:catalogue:manage
      - library:member:manage
      - library:policy:manage
      - library:circulation:manage
      - library:fine:manage
  - name: librarian
    description: Desk and cataloguing staff.
    grants:
      - library:catalogue:read
      - library:catalogue:manage
      - library:member:manage
      - library:circulation:manage
      - library:fine:manage
  - name: library-member
    description: Students, faculty and staff who borrow. Default for the student role.
    grants:
      - library:self:read
      - library:self:borrow
  - name: library-viewer
    description: Management and org admin oversight, read only.
    grants:
      - library:catalogue:read
`,pl=`# Permission catalogue for placement-career. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: placement-career
permissions: []
#  - key: placement-career:record:read
#    description: ...
#  - key: placement-career:record:write
#    description: ...
roles: []
#  - name: placement-career-admin
#    grants: [placement-career:record:read, placement-career:record:write]
`,ul=`# Permission catalogue for transport. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: transport
permissions:
  - key: transport:route:read
    description: View stops, routes and their assignments.
  - key: transport:route:manage
    description: Create and update stops and routes; assign vehicles and drivers to routes.
  - key: transport:vehicle:read
    description: View vehicles, drivers and compliance dates.
  - key: transport:vehicle:manage
    description: Add and update vehicles and drivers.
  - key: transport:pass:read
    description: View passes and pass requests.
  - key: transport:pass:manage
    description: Issue, reject and cancel passes.
  - key: transport:tracking:read
    description: View live trips and positions on every route.
  - key: transport:tracking:record
    description: Start and end trips, send positions, report delays and publish notices for the route the caller drives.
  - key: transport:notice:publish
    description: Publish and withdraw notices to any route.
  - key: transport:self:read
    description: View own passes and notices, routes and stops, and live position on routes with an issued pass.
  - key: transport:self:request
    description: Request a pass and cancel own pass.
roles:
  - name: transport-admin
    description: Transport office. Sets up routes, fleet and drivers and manages passes.
    grants:
      - transport:route:read
      - transport:route:manage
      - transport:vehicle:read
      - transport:vehicle:manage
      - transport:pass:read
      - transport:pass:manage
      - transport:tracking:read
      - transport:notice:publish
  - name: transport-driver
    description: Driver. Runs trips on the assigned route.
    grants:
      - transport:route:read
      - transport:tracking:record
  - name: transport-rider
    description: Students and staff who use transport. Default for the student role.
    grants:
      - transport:self:read
      - transport:self:request
  - name: transport-viewer
    description: Management and org admin oversight, read only.
    grants:
      - transport:route:read
      - transport:vehicle:read
      - transport:pass:read
      - transport:tracking:read
`,gl=`# Permission catalogue for asset-management. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: asset-management
permissions:
  - key: asset-management:asset:read
    description: See assets in one's care, their history and book value, and what is due for verification.
  - key: asset-management:asset:read-all
    description: See every asset in the organisation and the summary.
  - key: asset-management:asset:manage
    description: Register and edit assets and categories, transfer them, change their status, complete approved disposals.
  - key: asset-management:verification:perform
    description: See verification cycles and record results for assets.
  - key: asset-management:verification:manage
    description: Plan, start and close verification cycles.
  - key: asset-management:depreciation:read
    description: See depreciation schedules and runs.
  - key: asset-management:depreciation:manage
    description: Calculate, delete and post depreciation runs.
  - key: asset-management:disposal:request
    description: Request disposal of an asset in one's care and see own requests.
  - key: asset-management:disposal:approve
    description: Approve, reject or cancel disposal requests and see all of them.
roles:
  - name: asset-management-custodian
    description: Staff responsible for assets in their department or lab.
    grants: [asset-management:asset:read, asset-management:disposal:request]
  - name: asset-management-verifier
    description: Staff who carry out physical verification.
    grants: [asset-management:asset:read, asset-management:asset:read-all, asset-management:verification:perform]
  - name: asset-management-manager
    description: Facility / Inventory Staff. Runs the register and verification.
    grants: [asset-management:asset:read, asset-management:asset:read-all, asset-management:asset:manage, asset-management:verification:perform, asset-management:verification:manage, asset-management:depreciation:read, asset-management:disposal:request]
  - name: asset-management-finance
    description: Finance Staff. Depreciation and disposal decisions.
    grants: [asset-management:asset:read, asset-management:asset:read-all, asset-management:depreciation:read, asset-management:depreciation:manage, asset-management:disposal:approve]
  # Profile role (platform/identity/config/profiles). A token carries this, not the module roles above, so the
  # Facility / Inventory Staff dashboard (#331) needs it granted here: the same grants as asset-management-manager.
  - name: facility-staff
    description: The Facility / Inventory Staff profile role. Same grants as asset-management-manager.
    grants: [asset-management:asset:read, asset-management:asset:read-all, asset-management:asset:manage, asset-management:verification:perform, asset-management:verification:manage, asset-management:depreciation:read, asset-management:disposal:request]
`,hl=`# Permission catalogue for facility-booking. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Each academy profile maps its learner, approver and staff roles to the module roles below.
module: facility-booking
permissions:
  - key: facility-booking:resource:read
    description: Find resources, see their rules, opening hours, closures and free/busy availability.
  - key: facility-booking:resource:manage
    description: Create and edit resource types and resources, set opening hours and closures, take a resource out of service.
  - key: facility-booking:booking:read
    description: See own bookings, and bookings on resources the user approves.
  - key: facility-booking:booking:read-all
    description: See every booking in the organisation, including who holds a busy slot.
  - key: facility-booking:booking:create
    description: Book a resource for oneself, once or recurring, and edit or cancel own bookings before they start.
  - key: facility-booking:booking:approve
    description: Approve or reject pending bookings on resources where the user is a listed approver.
  - key: facility-booking:booking:manage
    description: Act on any booking. Book for others, approve or reject on any resource, cancel at any time, check in and record no-shows.
roles:
  - name: facility-booking-user
    description: Learners and instructors who book resources for themselves.
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: facility-booking-approver
    description: HoDs, lab in-charges and instructors who approve bookings for the resources they look after.
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: facility-booking-manager
    description: Facility / Inventory Staff. Runs the resource register and every booking.
    grants: [facility-booking:resource:read, facility-booking:resource:manage, facility-booking:booking:read, facility-booking:booking:read-all, facility-booking:booking:create, facility-booking:booking:approve, facility-booking:booking:manage]
  # Profile role (platform/identity/config/profiles). A token carries this, not the module roles above, so the
  # Facility / Inventory Staff dashboard (#331) needs it granted here: the same grants as facility-booking-manager.
  - name: facility-staff
    description: The Facility / Inventory Staff profile role. Same grants as facility-booking-manager.
    grants: [facility-booking:resource:read, facility-booking:resource:manage, facility-booking:booking:read, facility-booking:booking:read-all, facility-booking:booking:create, facility-booking:booking:approve, facility-booking:booking:manage]
  # Academy profile roles whose dashboards show this module's widgets (platform/identity/config/dashboards; follow-up
  # to #288, part of #331). Each gets the grants of the module role its PRD names for it.
  - name: actor
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: artist
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: dancer
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: designer
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: engineering-student
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: field-trainee
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: filmmaker
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: hospitality-trainee
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: medical-student
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: musician
    description: "Profile role, learner and performer roles: book a resource and see their own bookings (my-bookings). Same grants as facility-booking-user."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create]
  - name: chef-instructor
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: choreographer
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: clinical-supervisor
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: coach
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: director
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: equipment-manager
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: exhibition-manager
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: farm-supervisor
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: hospital-coordinator
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: lab-in-charge
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: medical-staff
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: music-teacher
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: production-manager
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: stage-manager
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
  - name: studio-instructor
    description: "Profile role, instructor and lead roles: approve bookings of the resources they look after (bookings-today, bookings). Same grants as facility-booking-approver."
    grants: [facility-booking:resource:read, facility-booking:booking:read, facility-booking:booking:create, facility-booking:booking:approve]
`,fl=`# Permission catalogue for inventory-equipment. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Each academy profile maps its borrower, approver and store staff roles to the module roles below.
module: inventory-equipment
permissions:
  - key: inventory-equipment:item:read
    description: Browse the catalogue, categories, locations and units, and see what is available.
  - key: inventory-equipment:item:manage
    description: Create and edit categories, locations, items and unit details.
  - key: inventory-equipment:stock:read
    description: See stock levels, the stock ledger and low-stock items.
  - key: inventory-equipment:stock:manage
    description: Receive, issue, transfer, adjust and write off stock; register units and change their status or condition.
  - key: inventory-equipment:loan:read
    description: See own loans, and loans of items the user approves.
  - key: inventory-equipment:loan:read-all
    description: See every loan in the organisation.
  - key: inventory-equipment:loan:request
    description: Request a loan for oneself, cancel it before hand-out, and extend it once.
  - key: inventory-equipment:loan:approve
    description: Approve or reject loan requests for categories where the user is a listed approver.
  - key: inventory-equipment:loan:manage
    description: Act on any loan. Lend to others, approve or reject any request, hand out, take back, extend and record losses.
roles:
  - name: inventory-equipment-borrower
    description: Learners and instructors who borrow items.
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request]
  - name: inventory-equipment-approver
    description: Instructors and leads who approve loans of the categories they look after.
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request, inventory-equipment:loan:approve]
  - name: inventory-equipment-manager
    description: Store staff (Facility / Inventory Staff, equipment manager, lab in-charge). Runs the catalogue, stores and every loan.
    grants: [inventory-equipment:item:read, inventory-equipment:item:manage, inventory-equipment:stock:read, inventory-equipment:stock:manage, inventory-equipment:loan:read, inventory-equipment:loan:read-all, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:loan:manage]
  # Profile role (platform/identity/config/profiles). A token carries this, not the module roles above, so the
  # Facility / Inventory Staff dashboard (#331) needs it granted here: the same grants as inventory-equipment-manager.
  - name: facility-staff
    description: The Facility / Inventory Staff profile role. Same grants as inventory-equipment-manager.
    grants: [inventory-equipment:item:read, inventory-equipment:item:manage, inventory-equipment:stock:read, inventory-equipment:stock:manage, inventory-equipment:loan:read, inventory-equipment:loan:read-all, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:loan:manage]
  # Academy profile roles whose dashboards show this module's widgets (platform/identity/config/dashboards; follow-up
  # to #288, part of #331). Each gets the grants of the module role its PRD names for it.
  - name: actor
    description: "Profile role, learner and performer roles: borrow items and see their own loans (my-loans). Same grants as inventory-equipment-borrower."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request]
  - name: artist
    description: "Profile role, learner and performer roles: borrow items and see their own loans (my-loans). Same grants as inventory-equipment-borrower."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request]
  - name: dancer
    description: "Profile role, learner and performer roles: borrow items and see their own loans (my-loans). Same grants as inventory-equipment-borrower."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request]
  - name: filmmaker
    description: "Profile role, learner and performer roles: borrow items and see their own loans (my-loans). Same grants as inventory-equipment-borrower."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request]
  - name: hospitality-trainee
    description: "Profile role, learner and performer roles: borrow items and see their own loans (my-loans). Same grants as inventory-equipment-borrower."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request]
  - name: musician
    description: "Profile role, learner and performer roles: borrow items and see their own loans (my-loans). Same grants as inventory-equipment-borrower."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request]
  - name: equipment-manager
    description: "Profile role, store staff named in the PRD: run the stores and every loan (low-stock, overdue-loans). Same grants as inventory-equipment-manager."
    grants: [inventory-equipment:item:read, inventory-equipment:item:manage, inventory-equipment:stock:read, inventory-equipment:stock:manage, inventory-equipment:loan:read, inventory-equipment:loan:read-all, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:loan:manage]
  - name: lab-in-charge
    description: "Profile role, store staff named in the PRD: run the stores and every loan (low-stock, overdue-loans). Same grants as inventory-equipment-manager."
    grants: [inventory-equipment:item:read, inventory-equipment:item:manage, inventory-equipment:stock:read, inventory-equipment:stock:manage, inventory-equipment:loan:read, inventory-equipment:loan:read-all, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:loan:manage]
  - name: chef-instructor
    description: "Profile role, leads who look after a store (PRD widgets table): approve loans and read stock levels (low-stock); stock:read is added read-only, without managing stock. Same grants as inventory-equipment-approver plus inventory-equipment:stock:read."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:stock:read]
  - name: ensemble-director
    description: "Profile role, leads who look after a store (PRD widgets table): approve loans and read stock levels (low-stock); stock:read is added read-only, without managing stock. Same grants as inventory-equipment-approver plus inventory-equipment:stock:read."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:stock:read]
  - name: exhibition-manager
    description: "Profile role, leads who look after a store (PRD widgets table): approve loans and read stock levels (low-stock); stock:read is added read-only, without managing stock. Same grants as inventory-equipment-approver plus inventory-equipment:stock:read."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:stock:read]
  - name: farm-supervisor
    description: "Profile role, leads who look after a store (PRD widgets table): approve loans and read stock levels (low-stock); stock:read is added read-only, without managing stock. Same grants as inventory-equipment-approver plus inventory-equipment:stock:read."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:stock:read]
  - name: production-manager
    description: "Profile role, leads who look after a store (PRD widgets table): approve loans and read stock levels (low-stock); stock:read is added read-only, without managing stock. Same grants as inventory-equipment-approver plus inventory-equipment:stock:read."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:stock:read]
  - name: stage-manager
    description: "Profile role, leads who look after a store (PRD widgets table): approve loans and read stock levels (low-stock); stock:read is added read-only, without managing stock. Same grants as inventory-equipment-approver plus inventory-equipment:stock:read."
    grants: [inventory-equipment:item:read, inventory-equipment:loan:read, inventory-equipment:loan:request, inventory-equipment:loan:approve, inventory-equipment:stock:read]
`,yl=`# Permission catalogue for maintenance. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: maintenance
permissions:
  - key: maintenance:ticket:create
    description: Report a fault, see categories, add notes to own tickets, confirm or reopen own resolved tickets.
  - key: maintenance:ticket:read
    description: See tickets one raised or is assigned, and the widget summary.
  - key: maintenance:ticket:read-all
    description: See every ticket in the organisation.
  - key: maintenance:ticket:work
    description: Work on assigned tickets. Start, hold, resume, resolve, log time, parts and cost.
  - key: maintenance:ticket:manage
    description: Triage, assign, change priority, close, cancel and reopen any ticket; manage categories.
  - key: maintenance:schedule:manage
    description: Create, change, pause and delete preventive schedules, and raise their tickets early.
roles:
  - name: maintenance-reporter
    description: Anyone in the organisation who reports faults.
    grants: [maintenance:ticket:create, maintenance:ticket:read]
  - name: maintenance-technician
    description: In-house technicians who carry out the work.
    grants: [maintenance:ticket:create, maintenance:ticket:read, maintenance:ticket:work]
  - name: maintenance-manager
    description: Facility / Inventory Staff, equipment manager, lab in-charge. Triage, assignment and planning.
    grants: [maintenance:ticket:create, maintenance:ticket:read, maintenance:ticket:read-all, maintenance:ticket:work, maintenance:ticket:manage, maintenance:schedule:manage]
  # Profile role (platform/identity/config/profiles). A token carries this, not the module roles above, so the
  # Facility / Inventory Staff dashboard (#331) needs it granted here: the same grants as maintenance-manager.
  - name: facility-staff
    description: The Facility / Inventory Staff profile role. Same grants as maintenance-manager.
    grants: [maintenance:ticket:create, maintenance:ticket:read, maintenance:ticket:read-all, maintenance:ticket:work, maintenance:ticket:manage, maintenance:schedule:manage]
  # Academy profile roles whose dashboards show this module's widgets (platform/identity/config/dashboards; follow-up
  # to #288, part of #331). Each gets the grants of the module role its PRD names for it.
  - name: equipment-manager
    description: "Profile role, store staff named in the PRD: triage and see every ticket (tickets). Same grants as maintenance-manager."
    grants: [maintenance:ticket:create, maintenance:ticket:read, maintenance:ticket:read-all, maintenance:ticket:work, maintenance:ticket:manage, maintenance:schedule:manage]
  - name: lab-in-charge
    description: "Profile role, store staff named in the PRD: triage and see every ticket (tickets). Same grants as maintenance-manager."
    grants: [maintenance:ticket:create, maintenance:ticket:read, maintenance:ticket:read-all, maintenance:ticket:work, maintenance:ticket:manage, maintenance:schedule:manage]
`,bl=`# Permission catalogue for sports-facilities. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: sports-facilities
permissions:
  - key: sports-facilities:facility:read
    description: View sports facilities, their spaces, operating hours and status
  - key: sports-facilities:facility:write
    description: Register facilities and edit their details, spaces and operating hours
  - key: sports-facilities:facility:status
    description: Open, limit or close a facility
  - key: sports-facilities:usage:read
    description: View usage records and utilisation
  - key: sports-facilities:usage:record
    description: Record facility usage
roles:
  - name: sports-facilities-admin
    description: Full administration of the sports facility registry and its usage
    grants:
      - sports-facilities:facility:read
      - sports-facilities:facility:write
      - sports-facilities:facility:status
      - sports-facilities:usage:read
      - sports-facilities:usage:record
  - name: sports-facilities-staff
    description: Facility staff keeping facilities, availability and usage up to date
    grants:
      - sports-facilities:facility:read
      - sports-facilities:facility:status
      - sports-facilities:usage:read
      - sports-facilities:usage:record
  - name: sports-facilities-coach
    description: Coaches checking facilities and logging the use of their squads
    grants:
      - sports-facilities:facility:read
      - sports-facilities:usage:read
      - sports-facilities:usage:record
  - name: sports-facilities-viewer
    description: Athletes and staff checking which facilities exist and are open
    grants:
      - sports-facilities:facility:read
`,xl=`# Permission catalogue for budget-grants. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: budget-grants
permissions:
  - key: budget-grants:budget:read
    description: View budget heads, budgets, reappropriations and expenditure.
  - key: budget-grants:budget:manage
    description: Create budget heads and budgets, submit them, request reappropriations.
  - key: budget-grants:budget:approve
    description: Approve or return budgets and decide reappropriations prepared by someone else.
  - key: budget-grants:availability:read
    description: List open budget and grant lines and check available amounts (used by procurement).
  - key: budget-grants:expenditure:record
    description: Record and reverse manual expenditure.
  - key: budget-grants:grant:read
    description: View all grants and their certificates.
  - key: budget-grants:grant:manage
    description: Record grants, funds received and closure; draft and mark certificates submitted.
  - key: budget-grants:utilisation:approve
    description: Certify utilisation certificates prepared by someone else.
  - key: budget-grants:report:read
    description: View budget-versus-spend reports.
  - key: budget-grants:self:read
    description: View grants where one is an investigator.
roles:
  - name: finance-staff
    grants:
      - budget-grants:budget:read
      - budget-grants:budget:manage
      - budget-grants:availability:read
      - budget-grants:expenditure:record
      - budget-grants:grant:read
      - budget-grants:grant:manage
      - budget-grants:utilisation:approve
      - budget-grants:report:read
  - name: research-office
    grants: [budget-grants:availability:read, budget-grants:grant:read, budget-grants:grant:manage, budget-grants:report:read]
  - name: management
    grants: [budget-grants:budget:read, budget-grants:budget:approve, budget-grants:availability:read, budget-grants:grant:read, budget-grants:utilisation:approve, budget-grants:report:read]
  - name: department-admin
    grants: [budget-grants:budget:read, budget-grants:availability:read, budget-grants:report:read, budget-grants:self:read]
  - name: org-admin
    grants: [budget-grants:budget:read, budget-grants:grant:read, budget-grants:report:read]
  - name: faculty
    grants: [budget-grants:availability:read, budget-grants:self:read]
  - name: research-supervisor
    grants: [budget-grants:availability:read, budget-grants:self:read]
  - name: research-scholar
    grants: [budget-grants:self:read]
`,vl=`# Permission catalogue for e-office. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# e-office:file:use is for every staff role; the roles below are the staff roles of the management institute
# profile. Other profiles' staff roles need the same grant (see docs/prd.md, open questions).
module: e-office
permissions:
  - key: e-office:file:use
    description: See files one has held; note, attach, forward and close files one holds; see one's inbox.
  - key: e-office:file:create
    description: Open new files and reopen closed ones.
  - key: e-office:file:decide
    description: Approve, reject or return a proposal as competent authority.
  - key: e-office:file:read-all
    description: See every non-confidential file of the organisation.
  - key: e-office:correspondence:manage
    description: Register inward correspondence and send outward dispatch (central registry).
  - key: e-office:report:read
    description: View pendency reports.
  - key: e-office:settings:manage
    description: Manage file categories.
roles:
  - name: hr-staff
    grants: [e-office:file:use, e-office:file:create, e-office:correspondence:manage]
  - name: finance-staff
    grants: [e-office:file:use, e-office:file:create]
  - name: department-admin
    grants: [e-office:file:use, e-office:file:create, e-office:file:decide, e-office:report:read]
  - name: management
    grants: [e-office:file:use, e-office:file:create, e-office:file:decide, e-office:file:read-all, e-office:report:read]
  - name: org-admin
    grants: [e-office:file:use, e-office:report:read, e-office:settings:manage]
  - name: faculty
    grants: [e-office:file:use, e-office:file:create]
  - name: examination-staff
    grants: [e-office:file:use, e-office:file:create]
  - name: facility-staff
    grants: [e-office:file:use, e-office:file:create]
  - name: support-staff
    grants: [e-office:file:use, e-office:file:create]
  - name: placement-officer
    grants: [e-office:file:use, e-office:file:create]
  - name: governance
    grants: [e-office:file:use, e-office:file:create]
`,wl=`# Permission catalogue for fees-accounts. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: fees-accounts
permissions:
  - key: fees-accounts:fee-structure:read
    description: View fee heads and fee structures.
  - key: fees-accounts:fee-structure:manage
    description: Create and edit fee heads; create, publish and archive fee structures.
  - key: fees-accounts:invoice:read
    description: View all invoices, payments and receipts of the organisation.
  - key: fees-accounts:invoice:create
    description: Raise invoices, one at a time or in bulk.
  - key: fees-accounts:invoice:cancel
    description: Cancel an invoice that has no payments.
  - key: fees-accounts:payment:record
    description: Record offline payments (cash, cheque, demand draft, bank transfer) and issue receipts.
  - key: fees-accounts:payment:refund
    description: Refund payments and void offline payments recorded in error.
  - key: fees-accounts:concession:request
    description: View concessions and request one on an invoice.
  - key: fees-accounts:concession:approve
    description: Approve or reject a concession requested by someone else.
  - key: fees-accounts:ledger:read
    description: View any person's fee statement.
  - key: fees-accounts:report:read
    description: View collection, outstanding and collection-versus-target reports.
  - key: fees-accounts:target:manage
    description: Set collection targets.
  - key: fees-accounts:dues:read
    description: Read any person's outstanding fee balance (GET /dues), for modules that gate a decision on dues.
  - key: fees-accounts:self:read
    description: View one's own dues, invoices and receipts.
  - key: fees-accounts:self:pay
    description: Pay one's own invoices online.
roles:
  - name: applicant
    grants: [fees-accounts:self:read, fees-accounts:self:pay]
  - name: student
    grants: [fees-accounts:self:read, fees-accounts:self:pay]
  - name: finance-staff
    grants:
      - fees-accounts:fee-structure:read
      - fees-accounts:fee-structure:manage
      - fees-accounts:invoice:read
      - fees-accounts:invoice:create
      - fees-accounts:invoice:cancel
      - fees-accounts:payment:record
      - fees-accounts:payment:refund
      - fees-accounts:concession:request
      - fees-accounts:ledger:read
      - fees-accounts:report:read
      - fees-accounts:dues:read
  - name: examination-staff
    grants: [fees-accounts:dues:read]
  - name: management
    grants: [fees-accounts:fee-structure:read, fees-accounts:report:read, fees-accounts:target:manage, fees-accounts:concession:approve]
  - name: org-admin
    grants: [fees-accounts:fee-structure:read, fees-accounts:invoice:read, fees-accounts:report:read, fees-accounts:target:manage]
`,kl=`# Permission catalogue for hr-payroll. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# hr-payroll:self:use is for every role held by an employee; the roles below are the staff roles of the
# management institute profile. Other profiles' staff roles need the same grant (see docs/prd.md, open questions).
module: hr-payroll
permissions:
  - key: hr-payroll:employee:read
    description: View employee records and service books.
  - key: hr-payroll:employee:manage
    description: Add, edit and exit employees; add service records; open appraisal cycles.
  - key: hr-payroll:leave-type:manage
    description: Create and edit leave types and entitlements.
  - key: hr-payroll:leave:approve
    description: View and decide leave requests (all, or one's reportees and department).
  - key: hr-payroll:payroll:read
    description: View salaries, payroll runs and payslips.
  - key: hr-payroll:payroll:prepare
    description: Set salaries, start and adjust payroll runs, submit them for approval.
  - key: hr-payroll:payroll:approve
    description: Approve or return a payroll run prepared by someone else; mark it paid.
  - key: hr-payroll:appraisal:review
    description: Review and rate appraisals (all, or one's reportees).
  - key: hr-payroll:report:read
    description: View HR reports such as joinings and exits.
  - key: hr-payroll:self:use
    description: View one's own record, leave balances and payslips; apply for leave; write one's self review.
roles:
  - name: hr-staff
    grants:
      - hr-payroll:employee:read
      - hr-payroll:employee:manage
      - hr-payroll:leave-type:manage
      - hr-payroll:leave:approve
      - hr-payroll:payroll:read
      - hr-payroll:payroll:prepare
      - hr-payroll:appraisal:review
      - hr-payroll:report:read
      - hr-payroll:self:use
  - name: finance-staff
    grants: [hr-payroll:payroll:read, hr-payroll:payroll:approve, hr-payroll:self:use]
  - name: department-admin
    grants: [hr-payroll:employee:read, hr-payroll:leave:approve, hr-payroll:appraisal:review, hr-payroll:self:use]
  - name: management
    grants: [hr-payroll:employee:read, hr-payroll:leave:approve, hr-payroll:payroll:read, hr-payroll:payroll:approve, hr-payroll:appraisal:review, hr-payroll:report:read, hr-payroll:self:use]
  - name: org-admin
    grants: [hr-payroll:employee:read, hr-payroll:report:read]
  - name: faculty
    grants: [hr-payroll:self:use]
  - name: examination-staff
    grants: [hr-payroll:self:use]
  - name: facility-staff
    grants: [hr-payroll:self:use]
  - name: support-staff
    grants: [hr-payroll:self:use]
  - name: placement-officer
    grants: [hr-payroll:self:use]
  - name: governance
    grants: [hr-payroll:self:use]
`,_l=`# Permission catalogue for procurement. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: procurement
permissions:
  - key: procurement:vendor:read
    description: View vendors.
  - key: procurement:vendor:manage
    description: Register and edit vendors; approve, suspend or blacklist them.
  - key: procurement:indent:create
    description: Raise, edit and submit one's own indents and follow them.
  - key: procurement:indent:approve
    description: >-
      View and decide indents raised by others. Limiting it to one's department is not enforced until identity
      issues a department claim; until then it covers every indent of the organisation.
  - key: procurement:tender:manage
    description: Create, publish and award quotation requests and tenders; record quotes.
  - key: procurement:purchase-order:read
    description: View purchase orders and goods receipts.
  - key: procurement:purchase-order:manage
    description: Create, edit and submit purchase orders.
  - key: procurement:purchase-order:approve
    description: Approve, return or cancel purchase orders prepared by someone else.
  - key: procurement:goods-receipt:record
    description: Record goods and services received against an order.
  - key: procurement:vendor-invoice:manage
    description: Record and view vendor invoices.
  - key: procurement:vendor-invoice:approve
    description: Approve for payment or reject vendor invoices recorded by someone else.
  - key: procurement:vendor-invoice:pay
    description: Record payment of approved vendor invoices.
  - key: procurement:report:read
    description: View procurement reports.
roles:
  - name: finance-staff
    grants:
      - procurement:vendor:read
      - procurement:vendor:manage
      - procurement:indent:create
      - procurement:tender:manage
      - procurement:purchase-order:read
      - procurement:purchase-order:manage
      - procurement:vendor-invoice:manage
      - procurement:vendor-invoice:approve
      - procurement:vendor-invoice:pay
      - procurement:report:read
  - name: management
    grants: [procurement:vendor:read, procurement:indent:approve, procurement:purchase-order:read, procurement:purchase-order:approve, procurement:vendor-invoice:approve, procurement:report:read]
  - name: department-admin
    grants: [procurement:indent:create, procurement:indent:approve, procurement:purchase-order:read]
  - name: facility-staff
    grants: [procurement:indent:create, procurement:purchase-order:read, procurement:goods-receipt:record]
  - name: faculty
    grants: [procurement:indent:create]
  - name: research-office
    grants: [procurement:indent:create, procurement:purchase-order:read]
  - name: org-admin
    grants: [procurement:vendor:read, procurement:purchase-order:read, procurement:report:read]
`,jl=`# Permission catalogue for grievance. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Case permissions are also limited on the server by committee membership (docs/prd.md "Confidentiality and access").
# Role names and their mapping to profile roles are a proposal: docs/prd.md open question 10.
module: grievance
permissions:
  - key: grievance:case:file
    description: File a complaint.
  - key: grievance:case:read-own
    description: See one's own cases (status, updates, decision, appeal; never proceedings); reply, withdraw and appeal.
  - key: grievance:case:read
    description: See case content, including proceedings, for cases of committees the caller is a member of.
  - key: grievance:case:manage
    description: Change status, message the complainant, record proceedings, decide and transfer cases of the caller's committees.
  - key: grievance:appeal:decide
    description: Decide appeals sent to an ombudsperson committee the caller is a member of.
  - key: grievance:committee:manage
    description: Create committees, change their members, and deactivate them. Gives no access to case content.
  - key: grievance:stats:read
    description: See counts of open and overdue cases per committee and per track. Gives no access to case content.
roles:
  - name: grievance-complainant
    description: Every signed-in person. Proposed default for all profile roles.
    grants:
      - grievance:case:file
      - grievance:case:read-own
  - name: grievance-committee-member
    description: People who sit on a committee. Each grant is still limited to that person's committees and committee kind.
    grants:
      - grievance:case:read
      - grievance:case:manage
      - grievance:appeal:decide
  - name: grievance-coordinator
    description: Sets up committees and sees counts, without case content. Proposed default for the governance profile role.
    grants:
      - grievance:committee:manage
      - grievance:stats:read
  - name: grievance-viewer
    description: Counts only. Proposed default for the management profile role.
    grants:
      - grievance:stats:read
`,Fl=`# Permission catalogue for iqac-accreditation. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Role names and their mapping to profile roles are a proposal: docs/prd.md open question 9.
module: iqac-accreditation
permissions:
  - key: iqac-accreditation:framework:manage
    description: Record and change frameworks and their metrics.
  - key: iqac-accreditation:cycle:manage
    description: Open and move cycles, assign metrics to owners, and accept or return responses.
  - key: iqac-accreditation:response:submit
    description: See, fill in and submit one's own responses, and add or remove their evidence; read frameworks and metrics.
  - key: iqac-accreditation:action-item:manage
    description: Record, change, reassign and cancel any action item.
  - key: iqac-accreditation:action-item:update-own
    description: See one's own action items and move them open → in_progress → done.
  - key: iqac-accreditation:data:read
    description: Read frameworks, metrics, cycles, all responses with evidence, and all action items.
  - key: iqac-accreditation:stats:read
    description: See the action-item counts behind the Governance widget.
roles:
  - name: iqac-accreditation-coordinator
    description: Runs IQAC work. Proposed default for the governance profile role.
    grants:
      - iqac-accreditation:framework:manage
      - iqac-accreditation:cycle:manage
      - iqac-accreditation:action-item:manage
      - iqac-accreditation:data:read
      - iqac-accreditation:stats:read
  - name: iqac-accreditation-contributor
    description: Owns metric responses and action items. Proposed default for the department-admin and faculty profile roles.
    grants:
      - iqac-accreditation:response:submit
      - iqac-accreditation:action-item:update-own
  - name: iqac-accreditation-viewer
    description: Read-only oversight. Proposed default for the management and org-admin profile roles.
    grants:
      - iqac-accreditation:data:read
      - iqac-accreditation:stats:read
`,Nl=`# Permission catalogue for regulatory-reports. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Role names and their mapping to profile roles are a proposal: docs/prd.md open question 10.
module: regulatory-reports
permissions:
  - key: regulatory-reports:obligation:manage
    description: Record, change and deactivate obligations.
  - key: regulatory-reports:filing:manage
    description: Create filings; change owner, due date and period; return, mark not applicable, submit and acknowledge any filing.
  - key: regulatory-reports:filing:prepare
    description: See one's own filings and their obligations; edit notes and links, start preparation and send for review.
  - key: regulatory-reports:data:read
    description: Read all obligations and filings; use scope=all on the due statistics; with stats:read, see the compliance calendar.
  - key: regulatory-reports:stats:read
    description: See the due statistics; with data:read, see the compliance calendar.
roles:
  - name: regulatory-reports-coordinator
    description: Runs statutory reporting. Proposed default for the governance profile role.
    grants:
      - regulatory-reports:obligation:manage
      - regulatory-reports:filing:manage
      - regulatory-reports:data:read
      - regulatory-reports:stats:read
  - name: regulatory-reports-preparer
    description: >-
      Prepares the filings they own. Proposed default for the hospital-coordinator, research-office, department-admin,
      finance-staff and hr-staff profile roles.
    grants:
      - regulatory-reports:filing:prepare
      - regulatory-reports:stats:read
  - name: regulatory-reports-viewer
    description: Read-only oversight and the compliance calendar. Proposed default for the management profile role.
    grants:
      - regulatory-reports:data:read
      - regulatory-reports:stats:read
`,Sl=`# Permission catalogue for rti. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Applicant personal data is visible only through rti:request:read. Role names and their mapping to profile roles are
# a proposal: docs/prd.md open question 10.
module: rti
permissions:
  - key: rti:request:read
    description: View requests, including applicant personal data, referrals, response, transfer and appeal.
  - key: rti:request:manage
    description: Record, correct, assign, refer, respond to, transfer and close requests.
  - key: rti:referral:respond
    description: See and answer one's own referrals only (question and request number; no applicant data).
  - key: rti:appeal:decide
    description: Record and decide first appeals.
  - key: rti:stats:read
    description: See counts and request numbers with due dates for open requests; no applicant data.
roles:
  - name: rti-officer
    description: Records and handles RTI requests. Proposed default for the governance profile role.
    grants:
      - rti:request:read
      - rti:request:manage
      - rti:stats:read
  - name: rti-custodian
    description: Answers referrals for information. Proposed default for the department-admin and faculty profile roles.
    grants:
      - rti:referral:respond
  - name: rti-appellate-authority
    description: Records and decides first appeals. Proposed default for the management profile role.
    grants:
      - rti:request:read
      - rti:appeal:decide
      - rti:stats:read
  - name: rti-viewer
    description: Counts and deadlines only. Proposed default for the org-admin profile role.
    grants:
      - rti:stats:read
`,El=`# Permission catalogue for field-training. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Roles below are generic. Each academy profile maps its own roles onto them (for example its trainee,
# supervisor and coordinator roles); the module never names an academy role.
module: field-training
permissions:
  - key: field-training:site:read
    description: View host sites.
  - key: field-training:site:manage
    description: Add and update host sites and their supervisors.
  - key: field-training:opening:read
    description: View every opening.
  - key: field-training:opening:manage
    description: Create, update, publish, close and cancel openings.
  - key: field-training:placement:read
    description: View every placement, its logbook and assessments.
  - key: field-training:placement:manage
    description: Assign, approve, reject, start, complete and withdraw placements; change supervisor or dates.
  - key: field-training:supervision:read
    description: View the placements the caller supervises, their logbooks and assessments, and openings at the caller's sites.
  - key: field-training:log:verify
    description: Verify or return log entries of placements the caller supervises.
  - key: field-training:assessment:record
    description: Record assessments of placements the caller supervises.
  - key: field-training:self:read
    description: View own placements, hours, log entries and assessments.
  - key: field-training:self:apply
    description: See open openings that accept applications, apply, and withdraw own placement before it starts.
  - key: field-training:self:log
    description: Add and edit own log entries.
roles:
  - name: field-training-coordinator
    description: Coordinates sites, openings and placements for the organisation.
    grants:
      - field-training:site:read
      - field-training:site:manage
      - field-training:opening:read
      - field-training:opening:manage
      - field-training:placement:read
      - field-training:placement:manage
  - name: field-training-supervisor
    description: Supervises trainees at a site; verifies logs and assesses.
    grants:
      - field-training:site:read
      - field-training:supervision:read
      - field-training:log:verify
      - field-training:assessment:record
  - name: field-training-trainee
    description: Learner who does placements.
    grants:
      - field-training:self:read
      - field-training:self:apply
      - field-training:self:log
  - name: field-training-viewer
    description: Management and org admin oversight, read only.
    grants:
      - field-training:site:read
      - field-training:opening:read
      - field-training:placement:read
`,Al=`# Permission catalogue for portfolio. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Each academy profile maps its learner, reviewer and staff roles to the module roles below.
module: portfolio
permissions:
  - key: portfolio:item-type:read
    description: See the item types configured for the organisation.
  - key: portfolio:item-type:manage
    description: Create and edit item types, including who may review each type.
  - key: portfolio:item:read
    description: See one's own items, and items one may review.
  - key: portfolio:item:read-all
    description: See every item in the organisation, regardless of owner or reviewer.
  - key: portfolio:item:write
    description: Create, edit, submit, withdraw and delete one's own items.
  - key: portfolio:item:manage
    description: Act on any item — create or edit for another person, submit, withdraw, delete at any status.
  - key: portfolio:review:write
    description: Review items of a type one is a named reviewer for.
  - key: portfolio:review:manage
    description: Review any item in the organisation, regardless of the item type's reviewer list.
roles:
  - name: portfolio-learner
    description: Learners who build and submit their own items.
    grants: [portfolio:item-type:read, portfolio:item:read, portfolio:item:write]
  - name: portfolio-reviewer
    description: Instructors or staff who review items of the types they are named on.
    grants: [portfolio:item-type:read, portfolio:item:read, portfolio:review:write]
  - name: portfolio-manager
    description: Runs the portfolio register for the organisation — configures types and may act on or review any item.
    grants: [portfolio:item-type:read, portfolio:item-type:manage, portfolio:item:read, portfolio:item:read-all, portfolio:item:write, portfolio:item:manage, portfolio:review:write, portfolio:review:manage]
`,Cl=`# Permission catalogue for productions. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: productions
permissions: []
#  - key: productions:record:read
#    description: ...
#  - key: productions:record:write
#    description: ...
roles: []
#  - name: productions-admin
#    grants: [productions:record:read, productions:record:write]
`,Pl=`# Permission catalogue for projects. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Roles below are generic. Each academy profile maps its own roles onto them (for example its learner,
# guide and coordinator roles); the module never names an academy role.
module: projects
permissions:
  - key: projects:project:read
    description: View every project with its team, milestones and submissions.
  - key: projects:project:manage
    description: Create projects, approve or reject proposals, change teams and guides, manage milestones, cancel projects.
  - key: projects:guidance:read
    description: View the projects the caller guides and the work awaiting their review.
  - key: projects:milestone:manage
    description: Add, change and cancel milestones of projects the caller guides.
  - key: projects:review:record
    description: Accept or return milestones and evaluate final submissions of projects the caller guides.
  - key: projects:self:read
    description: View own projects, milestones, submissions and feedback.
  - key: projects:self:propose
    description: Propose a project and, as its lead while proposed, edit it and its team.
  - key: projects:self:submit
    description: Submit milestones and the final work of own projects.
roles:
  - name: projects-coordinator
    description: Coordinates projects for the organisation; approves proposals and assigns guides.
    grants:
      - projects:project:read
      - projects:project:manage
  - name: projects-guide
    description: Guides project teams; sets milestones, reviews and evaluates.
    grants:
      - projects:guidance:read
      - projects:milestone:manage
      - projects:review:record
  - name: projects-member
    description: Learner who works on projects.
    grants:
      - projects:self:read
      - projects:self:propose
      - projects:self:submit
  - name: projects-viewer
    description: Management and org admin oversight, read only.
    grants:
      - projects:project:read
`,Rl=`# Permission catalogue for selection-process. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Each academy profile maps its panelist, coordinator and staff roles to the module roles below.
module: selection-process
permissions:
  - key: selection-process:process-type:read
    description: See the process types configured for the organisation.
  - key: selection-process:process-type:manage
    description: Create and edit process types.
  - key: selection-process:process:read
    description: See processes, their stages and panels.
  - key: selection-process:process:manage
    description: Create, edit, open and close processes and their stages.
  - key: selection-process:panel:manage
    description: Create and edit panels and their membership.
  - key: selection-process:candidate:read
    description: See one's own candidacy, or a candidate on a stage one panels.
  - key: selection-process:candidate:read-all
    description: See every candidate on every process in the organisation.
  - key: selection-process:candidate:manage
    description: Register or withdraw a candidate on a process.
  - key: selection-process:decision:write
    description: Record a decision for a candidate on a stage one panels.
  - key: selection-process:decision:manage
    description: Record or override a decision on any candidate, and finalize an outcome directly.
roles:
  - name: selection-process-panelist
    description: Judges or reviewers on one or more panels.
    grants: [selection-process:process-type:read, selection-process:process:read, selection-process:candidate:read, selection-process:decision:write]
  - name: selection-process-coordinator
    description: Runs a selection process end to end — configures types, processes, stages and panels, and may decide or override any outcome.
    grants: [selection-process:process-type:read, selection-process:process-type:manage, selection-process:process:read, selection-process:process:manage, selection-process:panel:manage, selection-process:candidate:read, selection-process:candidate:read-all, selection-process:candidate:manage, selection-process:decision:write, selection-process:decision:manage]
  - name: org-admin
    description: Read-only visibility into the organisation's selection activity.
    grants: [selection-process:process:read]
`,Ml=`# Permission catalogue for skill-progress. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: skill-progress
permissions:
  - key: skill-progress:framework:read
    description: View skill frameworks, competencies, and rubrics
  - key: skill-progress:framework:write
    description: Create, edit, and archive skill frameworks and rubrics
  - key: skill-progress:assessment:read
    description: View skill assessments and evaluation records
  - key: skill-progress:assessment:record
    description: Record and submit assessments and skill evaluations
  - key: skill-progress:assessment:approve
    description: Review, verify, or finalize recorded skill assessments
  - key: skill-progress:assessment:delete
    description: Void or remove an assessment record
  - key: skill-progress:progress:read
    description: View learner skill progression, proficiency levels, and timelines
  - key: skill-progress:progress:export
    description: Export learner competency reports and progress metrics
roles:
  - name: skill-progress-admin
    description: Full administration of frameworks, rubrics, assessments, and progress records
    grants:
      - skill-progress:framework:read
      - skill-progress:framework:write
      - skill-progress:assessment:read
      - skill-progress:assessment:record
      - skill-progress:assessment:approve
      - skill-progress:assessment:delete
      - skill-progress:progress:read
      - skill-progress:progress:export
  - name: skill-progress-evaluator
    description: Evaluators, instructors, mentors, and supervisors recording skill assessments
    grants:
      - skill-progress:framework:read
      - skill-progress:assessment:read
      - skill-progress:assessment:record
      - skill-progress:progress:read
  - name: skill-progress-viewer
    description: Learners and observers viewing skill frameworks and individual progress
    grants:
      - skill-progress:framework:read
      - skill-progress:assessment:read
      - skill-progress:progress:read

`,Dl=`# Permission catalogue for athlete-performance. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Athletes see only their own profile, results and assessments: the module filters rows by the
# caller's athlete record; the keys below say which kinds of data a role may use at all.
module: athlete-performance
permissions:
  - key: athlete-performance:catalogue:read
    description: View disciplines, metric definitions and fitness tests
  - key: athlete-performance:catalogue:write
    description: Create and manage disciplines, metric definitions and fitness tests
  - key: athlete-performance:athlete:read
    description: View athlete profiles
  - key: athlete-performance:athlete:write
    description: Create and update athlete profiles
  - key: athlete-performance:result:read
    description: View performance results and history
  - key: athlete-performance:result:record
    description: Record and correct performance results
  - key: athlete-performance:assessment:read
    description: View fitness assessments
  - key: athlete-performance:assessment:record
    description: Record fitness assessments
  - key: athlete-performance:benchmark:read
    description: View benchmarks and compare athletes with them
  - key: athlete-performance:benchmark:write
    description: Create and change benchmarks
  - key: athlete-performance:clearance:read
    description: View athletes' fitness clearance status
  - key: athlete-performance:clearance:write
    description: Set athletes' fitness clearance (medical staff)
  - key: athlete-performance:report:read
    description: View squad and performance summary reports
roles:
  - name: athlete-performance-admin
    description: Full administration of the catalogue, athletes, results, assessments, benchmarks and clearances
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:catalogue:write
      - athlete-performance:athlete:read
      - athlete-performance:athlete:write
      - athlete-performance:result:read
      - athlete-performance:result:record
      - athlete-performance:assessment:read
      - athlete-performance:assessment:record
      - athlete-performance:benchmark:read
      - athlete-performance:benchmark:write
      - athlete-performance:clearance:read
      - athlete-performance:clearance:write
      - athlete-performance:report:read
  - name: athlete-performance-coach
    description: Coaches managing their athletes, recording results and assessments, and setting benchmarks
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:athlete:write
      - athlete-performance:result:read
      - athlete-performance:result:record
      - athlete-performance:assessment:read
      - athlete-performance:assessment:record
      - athlete-performance:benchmark:read
      - athlete-performance:benchmark:write
      - athlete-performance:clearance:read
      - athlete-performance:report:read
  - name: athlete-performance-medical
    description: Medical staff recording fitness assessments and setting fitness clearance
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:result:read
      - athlete-performance:assessment:read
      - athlete-performance:assessment:record
      - athlete-performance:clearance:read
      - athlete-performance:clearance:write
  - name: athlete-performance-athlete
    description: Athletes viewing their own profile, results, assessments, benchmarks and clearance
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:result:read
      - athlete-performance:assessment:read
      - athlete-performance:benchmark:read
      - athlete-performance:clearance:read
  - name: athlete-performance-viewer
    description: Management and authorised staff reading performance summaries
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:report:read
  # The sports-college profile's own roles (platform/identity/config/profiles/sports-college.yaml), so the people an
  # institution creates there can use this module without also holding an athlete-performance-* role.
  - name: coach
    description: Coach (profile role); same access as athlete-performance-coach
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:athlete:write
      - athlete-performance:result:read
      - athlete-performance:result:record
      - athlete-performance:assessment:read
      - athlete-performance:assessment:record
      - athlete-performance:benchmark:read
      - athlete-performance:benchmark:write
      - athlete-performance:clearance:read
      - athlete-performance:report:read
  - name: medical-staff
    description: Medical Staff (profile role); same access as athlete-performance-medical
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:result:read
      - athlete-performance:assessment:read
      - athlete-performance:assessment:record
      - athlete-performance:clearance:read
      - athlete-performance:clearance:write
  - name: athlete
    description: Athlete (profile role); their own data only, same as athlete-performance-athlete
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:result:read
      - athlete-performance:assessment:read
      - athlete-performance:benchmark:read
      - athlete-performance:clearance:read
  - name: nutritionist
    description: Nutritionist (profile role); reads athletes and performance summaries, same as athlete-performance-viewer
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:report:read
  - name: management
    description: Management (profile role); reads performance summaries, same as athlete-performance-viewer
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:athlete:read
      - athlete-performance:report:read
  - name: org-admin
    description: Organisation Admin (profile role); full administration, same as athlete-performance-admin
    grants:
      - athlete-performance:catalogue:read
      - athlete-performance:catalogue:write
      - athlete-performance:athlete:read
      - athlete-performance:athlete:write
      - athlete-performance:result:read
      - athlete-performance:result:record
      - athlete-performance:assessment:read
      - athlete-performance:assessment:record
      - athlete-performance:benchmark:read
      - athlete-performance:benchmark:write
      - athlete-performance:clearance:read
      - athlete-performance:clearance:write
      - athlete-performance:report:read
`,Ol=`# Permission catalogue for sports-nutrition-health. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Health records are confidential: only medical roles hold health-record keys. Athletes see only
# their own plans, injuries and appointments (rows filtered by the caller's athlete record).
module: sports-nutrition-health
permissions:
  - key: sports-nutrition-health:plan:read
    description: View nutrition plans and their reviews
  - key: sports-nutrition-health:plan:write
    description: Create and update nutrition plans
  - key: sports-nutrition-health:plan:review
    description: Record nutrition plan reviews
  - key: sports-nutrition-health:health-record:read
    description: View confidential health records (medical history, allergies, medication, screenings)
  - key: sports-nutrition-health:health-record:write
    description: Create and update confidential health records
  - key: sports-nutrition-health:injury:read
    description: View injuries, their status and expected return dates
  - key: sports-nutrition-health:injury:write
    description: Report injuries and update their recovery
  - key: sports-nutrition-health:appointment:read
    description: View physiotherapy, medical and nutrition appointments
  - key: sports-nutrition-health:appointment:write
    description: Schedule and update appointments
roles:
  - name: sports-nutrition-health-admin
    description: Full administration of plans, health records, injuries and appointments
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:plan:write
      - sports-nutrition-health:plan:review
      - sports-nutrition-health:health-record:read
      - sports-nutrition-health:health-record:write
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:injury:write
      - sports-nutrition-health:appointment:read
      - sports-nutrition-health:appointment:write
  - name: sports-nutrition-health-medical
    description: Doctors and physiotherapists managing health records, injuries and appointments
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:health-record:read
      - sports-nutrition-health:health-record:write
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:injury:write
      - sports-nutrition-health:appointment:read
      - sports-nutrition-health:appointment:write
  - name: sports-nutrition-health-nutritionist
    description: Nutritionists building and reviewing diet plans
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:plan:write
      - sports-nutrition-health:plan:review
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:appointment:read
      - sports-nutrition-health:appointment:write
  - name: sports-nutrition-health-coach
    description: Coaches seeing who is injured and on which plan, without clinical records
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:appointment:read
  - name: sports-nutrition-health-athlete
    description: Athletes viewing their own plans, injuries and appointments
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:appointment:read
  # The sports-college profile's own roles (platform/identity/config/profiles/sports-college.yaml), so the people an
  # institution creates there can use this module without also holding a sports-nutrition-health-* role. Health
  # records stay with medical roles: org-admin administers plans, injuries and appointments but not health records.
  - name: medical-staff
    description: Medical Staff (profile role); same access as sports-nutrition-health-medical
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:health-record:read
      - sports-nutrition-health:health-record:write
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:injury:write
      - sports-nutrition-health:appointment:read
      - sports-nutrition-health:appointment:write
  - name: nutritionist
    description: Nutritionist (profile role); same access as sports-nutrition-health-nutritionist
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:plan:write
      - sports-nutrition-health:plan:review
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:appointment:read
      - sports-nutrition-health:appointment:write
  - name: coach
    description: Coach (profile role); same access as sports-nutrition-health-coach
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:appointment:read
  - name: athlete
    description: Athlete (profile role); their own data only, same as sports-nutrition-health-athlete
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:appointment:read
  - name: org-admin
    description: Organisation Admin (profile role); plans, injuries and appointments, without health records
    grants:
      - sports-nutrition-health:plan:read
      - sports-nutrition-health:plan:write
      - sports-nutrition-health:plan:review
      - sports-nutrition-health:injury:read
      - sports-nutrition-health:injury:write
      - sports-nutrition-health:appointment:read
      - sports-nutrition-health:appointment:write
`,Tl=`# Permission catalogue for tournament-events. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Draft tournaments are visible only to holders of tournament:write.
module: tournament-events
permissions:
  - key: tournament-events:tournament:read
    description: View published tournaments and the calendar
  - key: tournament-events:tournament:write
    description: Create tournaments and edit drafts
  - key: tournament-events:tournament:publish
    description: Publish or cancel a tournament
  - key: tournament-events:entry:read
    description: View entries
  - key: tournament-events:entry:write
    description: Enter athletes or teams, confirm or withdraw entries
  - key: tournament-events:fixture:read
    description: View fixtures
  - key: tournament-events:fixture:write
    description: Schedule and update fixtures
  - key: tournament-events:result:read
    description: View results
  - key: tournament-events:result:record
    description: Record fixture results
  - key: tournament-events:official:read
    description: View assigned officials
  - key: tournament-events:official:write
    description: Assign and remove officials
  - key: tournament-events:logistics:read
    description: View travel and event logistics
  - key: tournament-events:logistics:write
    description: Set travel and event logistics
roles:
  - name: tournament-events-admin
    description: Full administration of tournaments, entries, fixtures, results, officials and logistics
    grants:
      - tournament-events:tournament:read
      - tournament-events:tournament:write
      - tournament-events:tournament:publish
      - tournament-events:entry:read
      - tournament-events:entry:write
      - tournament-events:fixture:read
      - tournament-events:fixture:write
      - tournament-events:result:read
      - tournament-events:result:record
      - tournament-events:official:read
      - tournament-events:official:write
      - tournament-events:logistics:read
      - tournament-events:logistics:write
  - name: tournament-events-coach
    description: Coaches entering athletes, following fixtures and recording results
    grants:
      - tournament-events:tournament:read
      - tournament-events:entry:read
      - tournament-events:entry:write
      - tournament-events:fixture:read
      - tournament-events:result:read
      - tournament-events:result:record
      - tournament-events:official:read
      - tournament-events:logistics:read
  - name: tournament-events-athlete
    description: Athletes viewing tournaments, their entries, fixtures, results and travel plans
    grants:
      - tournament-events:tournament:read
      - tournament-events:entry:read
      - tournament-events:fixture:read
      - tournament-events:result:read
      - tournament-events:logistics:read
  - name: tournament-events-viewer
    description: Management and staff following the tournament calendar and results
    grants:
      - tournament-events:tournament:read
      - tournament-events:fixture:read
      - tournament-events:result:read
`,Bl=`# Permission catalogue for training-video-analysis. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: training-video-analysis
permissions:
  - key: training-video-analysis:plan:read
    description: View training plans and seasonal schedules
  - key: training-video-analysis:plan:write
    description: Create and manage training plans
  - key: training-video-analysis:session:read
    description: View training sessions, schedules, and attendance
  - key: training-video-analysis:session:write
    description: Schedule and manage training sessions
  - key: training-video-analysis:drill:read
    description: View drill repository and catalogs
  - key: training-video-analysis:drill:write
    description: Create and manage drills in repository
  - key: training-video-analysis:video:read
    description: View and playback training videos and analysis
  - key: training-video-analysis:video:upload
    description: Upload and register new training videos
  - key: training-video-analysis:video:tag
    description: Tag drills and segments on video timeline
  - key: training-video-analysis:annotation:write
    description: Add and manage coaching annotations and markup on video
roles:
  - name: training-video-analysis-admin
    description: Full administration of training plans, sessions, video repository, and annotations
    grants:
      - training-video-analysis:plan:read
      - training-video-analysis:plan:write
      - training-video-analysis:session:read
      - training-video-analysis:session:write
      - training-video-analysis:drill:read
      - training-video-analysis:drill:write
      - training-video-analysis:video:read
      - training-video-analysis:video:upload
      - training-video-analysis:video:tag
      - training-video-analysis:annotation:write
  - name: training-video-analysis-coach
    description: Coaches creating sessions, tagging drills, and annotating video for athletes
    grants:
      - training-video-analysis:plan:read
      - training-video-analysis:plan:write
      - training-video-analysis:session:read
      - training-video-analysis:session:write
      - training-video-analysis:drill:read
      - training-video-analysis:drill:write
      - training-video-analysis:video:read
      - training-video-analysis:video:upload
      - training-video-analysis:video:tag
      - training-video-analysis:annotation:write
  - name: training-video-analysis-athlete
    description: Athletes viewing their assigned training plans, sessions, and reviewed videos
    grants:
      - training-video-analysis:plan:read
      - training-video-analysis:session:read
      - training-video-analysis:drill:read
      - training-video-analysis:video:read

  # The sports-college profile's own roles (platform/identity/config/profiles/sports-college.yaml). The coach layout
  # already holds training-video-analysis-coach through its module_roles; the athlete and org-admin layouts do not.
  - name: athlete
    description: Athlete (profile role); their own sessions, plans and videos only, same as training-video-analysis-athlete
    grants:
      - training-video-analysis:plan:read
      - training-video-analysis:session:read
      - training-video-analysis:drill:read
      - training-video-analysis:video:read
  - name: org-admin
    description: Organisation Admin (profile role); full administration, same as training-video-analysis-admin
    grants:
      - training-video-analysis:plan:read
      - training-video-analysis:plan:write
      - training-video-analysis:session:read
      - training-video-analysis:session:write
      - training-video-analysis:drill:read
      - training-video-analysis:drill:write
      - training-video-analysis:video:read
      - training-video-analysis:video:upload
      - training-video-analysis:video:tag
      - training-video-analysis:annotation:write
`,Ll=`# Permission catalogue for admissions. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Public endpoints (submit, track, document upload, offer accept/decline) need no permission key;
# they are unauthenticated by design (docs/prd.md §6) and are not listed below.
module: admissions
permissions:
  - key: admissions:application:read
    description: List and view applications in the organisation.
  - key: admissions:application:manage
    description: Move an application through staff-driven status transitions (under_review, eligible, ineligible, rejected, staff-initiated withdrawn).
  - key: admissions:document:verify
    description: Verify or reject a document attached to an application.
  - key: admissions:merit-list:manage
    description: Generate and publish merit lists.
  - key: admissions:offer:manage
    description: Extend an offer on an eligible application.
  - key: admissions:report:read
    description: Read admissions funnel counts. Counts only, no applicant personal data.
roles:
  - name: admissions-reviewer
    description: Reviews documents and eligibility but does not decide offers or merit lists.
    grants: [admissions:application:read, admissions:document:verify]
  - name: admissions-staff
    description: Runs the full admissions funnel for the organisation.
    grants: [admissions:application:read, admissions:application:manage, admissions:document:verify, admissions:merit-list:manage, admissions:offer:manage, admissions:report:read]
  - name: department-admin
    description: Reviews applications and merit lists for their department's programmes.
    grants: [admissions:application:read, admissions:merit-list:manage, admissions:report:read]
  - name: management
    description: VC and Registrar. Sees the admissions funnel; no access to individual applications.
    grants: [admissions:report:read]
  - name: org-admin
    description: Read-only visibility into the organisation's admissions activity.
    grants: [admissions:application:read, admissions:report:read]
`,Il=`# Permission catalogue for enrolment-registration. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: enrolment-registration
permissions:
  - key: enrolment-registration:enrolment:read
    description: List and read programme enrolments and roll numbers.
  - key: enrolment-registration:enrolment:manage
    description: Enrol a person in a programme; withdraw or complete an enrolment.
  - key: enrolment-registration:registration:read
    description: List and read course registrations and registration windows; read the registered-candidates report.
  - key: enrolment-registration:registration:manage
    description: Set registration windows; register, withdraw and move course registrations.
roles:
  - name: registration-staff
    description: Academic office staff who enrol students and run course registration.
    grants: [enrolment-registration:enrolment:read, enrolment-registration:enrolment:manage, enrolment-registration:registration:read, enrolment-registration:registration:manage]
  - name: org-admin
    description: Organisation admin. Every key, so an organisation can enrol and register students before it has registration staff.
    grants: [enrolment-registration:enrolment:read, enrolment-registration:enrolment:manage, enrolment-registration:registration:read, enrolment-registration:registration:manage]
  - name: management
    description: VC and Registrar. Read-only visibility into enrolments and registrations.
    grants: [enrolment-registration:enrolment:read, enrolment-registration:registration:read]
  - name: department-admin
    description: Reads enrolments and registrations.
    grants: [enrolment-registration:enrolment:read, enrolment-registration:registration:read]
  - name: examination-staff
    description: Sees who is registered, to plan exams (registered-candidates widget).
    grants: [enrolment-registration:registration:read]
`,ql=`# Permission catalogue for student-information. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: student-information
permissions:
  - key: student-information:person:read
    description: Read a person's profile, contact details, documents, ID cards and status.
  - key: student-information:person:write
    description: >-
      Create a person record and update profile fields. Creation is staff-only; this module has
      no public or anonymous path, and no permission here is ever granted to an unauthenticated
      caller or an organisation sign-up flow.
  - key: student-information:status:manage
    description: Change a person's status (pending, active, suspended, graduated, withdrawn, alumnus) and view status history.
  - key: student-information:document:manage
    description: Attach or remove documents on a person's record.
  - key: student-information:id-card:manage
    description: Issue or revoke a person's ID card.
# Roles are granted here because platform/identity composes permissions only from the roles listed in
# every contracts/permissions.yaml (eos_core.config.permissions_for); profiles name roles but hold no grants.
# \`registrar\` is the module's own role; \`org-admin\`, \`management\` and \`admissions-staff\` are catalogue roles.
roles:
  - name: registrar
    description: Registrar / student-information staff. Creates and maintains records, changes status, issues ID cards.
    grants:
      - student-information:person:read
      - student-information:person:write
      - student-information:status:manage
      - student-information:document:manage
      - student-information:id-card:manage
  - name: org-admin
    description: Organisation admin. Full access to the organisation's people records.
    grants:
      - student-information:person:read
      - student-information:person:write
      - student-information:status:manage
      - student-information:document:manage
      - student-information:id-card:manage
  - name: management
    description: Management oversight, read only.
    grants:
      - student-information:person:read
  - name: admissions-staff
    description: Admissions staff converting an accepted applicant into a Person record (docs/prd.md section 6).
    grants:
      - student-information:person:read
      - student-information:person:write
`,$l=`# Permission catalogue for web-portal-cms. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# The registration pages need no key: they call platform/tenancy's public endpoints, not this module's.
module: web-portal-cms
permissions:
  - key: web-portal-cms:page:read
    description: List and read the organisation's published pages.
  - key: web-portal-cms:page:manage
    description: Create, edit, publish, unpublish and delete pages; see drafts.
  - key: web-portal-cms:announcement:read
    description: List and read the organisation's visible announcements (published and within their window).
  - key: web-portal-cms:announcement:manage
    description: Create, edit, publish, unpublish and delete announcements; see drafts and out-of-window ones.
roles:
  - name: member
    description: Implicit. Every organisation user holds it (platform/tenancy/contracts/permissions.yaml); reads the CMS.
    grants: [web-portal-cms:page:read, web-portal-cms:announcement:read]
  - name: web-portal-cms-editor
    description: Organisation staff who maintain the organisation's pages and announcements.
    grants: [web-portal-cms:page:read, web-portal-cms:page:manage, web-portal-cms:announcement:read, web-portal-cms:announcement:manage]
  - name: org-admin
    description: Full control over their own organisation's pages and announcements.
    grants: [web-portal-cms:page:read, web-portal-cms:page:manage, web-portal-cms:announcement:read, web-portal-cms:announcement:manage]
`,Vl=`# Permission catalogue for amc-vendor-support. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Role names and their mapping to profile roles are a proposal: docs/prd.md open question 6.
module: amc-vendor-support
permissions:
  - key: amc-vendor-support:contract:read
    description: View contracts, covered items, coverage, engagements and the expiring-contracts statistics.
  - key: amc-vendor-support:contract:manage
    description: Record, edit, activate, renew and terminate contracts; add and remove covered items.
  - key: amc-vendor-support:engagement:manage
    description: Raise engagements with a vendor, update them and move them through their statuses.
roles:
  - name: amc-vendor-support-coordinator
    description: Raises and tracks vendor calls and visits. Proposed default for the support-staff and facility-staff profile roles.
    grants:
      - amc-vendor-support:contract:read
      - amc-vendor-support:engagement:manage
  - name: amc-vendor-support-contract-manager
    description: Records and manages AMC contracts and their renewals. Proposed default for the org-admin profile role.
    grants:
      - amc-vendor-support:contract:read
      - amc-vendor-support:contract:manage
      - amc-vendor-support:engagement:manage
  - name: amc-vendor-support-viewer
    description: Read-only oversight. Proposed default for the management and finance-staff profile roles.
    grants:
      - amc-vendor-support:contract:read
`,Hl=`# Permission catalogue for helpdesk. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: helpdesk
permissions:
  - key: helpdesk:ticket:read
    description: View tickets in the queues the caller belongs to, with internal notes, and the open-by-priority counts.
  - key: helpdesk:ticket:read-all
    description: View tickets in every queue.
  - key: helpdesk:ticket:work
    description: Raise tickets on behalf of others, pick up tickets in own queues, reply, add internal notes, hold, resolve and link.
  - key: helpdesk:ticket:manage
    description: Assign and move tickets between queues, change category and priority of any ticket, cancel tickets and duplicates.
  - key: helpdesk:settings:manage
    description: Create and update support queues, their members, and ticket categories.
  - key: helpdesk:self:read
    description: View own tickets and the public replies on them.
  - key: helpdesk:self:raise
    description: Raise tickets for oneself, reply, confirm, reopen and withdraw own tickets.
roles:
  - name: helpdesk-requester
    description: Every signed-in person (student, faculty, staff, applicant). Default for all profile roles.
    grants:
      - helpdesk:self:read
      - helpdesk:self:raise
  - name: helpdesk-agent
    description: Support staff working tickets in their queues. Default for the support-staff profile role.
    grants:
      - helpdesk:self:read
      - helpdesk:self:raise
      - helpdesk:ticket:read
      - helpdesk:ticket:work
  - name: helpdesk-lead
    description: Support supervisor. Works and manages tickets across every queue.
    grants:
      - helpdesk:self:read
      - helpdesk:self:raise
      - helpdesk:ticket:read
      - helpdesk:ticket:read-all
      - helpdesk:ticket:work
      - helpdesk:ticket:manage
  - name: helpdesk-admin
    description: Sets up queues and categories. Default for org-admin.
    grants:
      - helpdesk:self:read
      - helpdesk:self:raise
      - helpdesk:ticket:read
      - helpdesk:ticket:read-all
      - helpdesk:settings:manage
  - name: helpdesk-viewer
    description: Management oversight, read only, across every queue. Default for management.
    grants:
      - helpdesk:self:read
      - helpdesk:self:raise
      - helpdesk:ticket:read
      - helpdesk:ticket:read-all
  # Profile roles (platform/identity/config/profiles). A token carries these, not the helpdesk-* roles above, so
  # each default named above is granted here too, as hostel does for student.
  - name: support-staff
    description: The Support Staff (Helpdesk) profile role. Same grants as helpdesk-agent.
    grants:
      - helpdesk:self:read
      - helpdesk:self:raise
      - helpdesk:ticket:read
      - helpdesk:ticket:work
  - name: org-admin
    description: The organisation admin. Same grants as helpdesk-admin.
    grants:
      - helpdesk:self:read
      - helpdesk:self:raise
      - helpdesk:ticket:read
      - helpdesk:ticket:read-all
      - helpdesk:settings:manage
  - name: management
    description: The Management profile role (VC, Registrar). Same grants as helpdesk-viewer.
    grants:
      - helpdesk:self:read
      - helpdesk:self:raise
      - helpdesk:ticket:read
      - helpdesk:ticket:read-all
`,Ul=`# Permission catalogue for incident-management. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: incident-management
permissions:
  - key: incident-management:incident:read
    description: View incidents with their timeline and references, and the open-incident counts.
  - key: incident-management:incident:report
    description: Report an incident.
  - key: incident-management:incident:manage
    description: Change an incident's status, severity, details, lead and responders; add timeline updates and references; link it to a problem.
  - key: incident-management:problem:read
    description: View problems, RCAs and corrective actions; mark one's own corrective action done.
  - key: incident-management:problem:manage
    description: Open and move problems, draft and publish RCAs, create and change corrective actions.
roles:
  - name: incident-management-responder
    description: Support staff who report and work incidents. Default for the support-staff profile role.
    grants:
      - incident-management:incident:read
      - incident-management:incident:report
      - incident-management:incident:manage
      - incident-management:problem:read
  - name: incident-management-problem-manager
    description: Support lead who also runs problems and root-cause analysis.
    grants:
      - incident-management:incident:read
      - incident-management:incident:report
      - incident-management:incident:manage
      - incident-management:problem:read
      - incident-management:problem:manage
  - name: incident-management-viewer
    description: Read-only oversight. Default for the management and org-admin profile roles.
    grants:
      - incident-management:incident:read
      - incident-management:problem:read
`,Gl=`# Permission catalogue for knowledge-base. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: knowledge-base
permissions:
  - key: knowledge-base:article:read
    description: Browse, search and read published articles for everyone, see categories, and give feedback.
  - key: knowledge-base:article:read-internal
    description: Also read published staff-only articles.
  - key: knowledge-base:article:write
    description: >-
      Create articles; edit, submit and discard own drafts; change own articles' settings (owner_id, review_by); see
      drafts, review states and revision history.
  - key: knowledge-base:article:publish
    description: Return, publish, archive and restore articles; edit or discard any draft; change article settings.
  - key: knowledge-base:category:manage
    description: Create, rename, move, reorder and deactivate categories.
  - key: knowledge-base:stats:read
    description: See feedback comments and article usage, including the top-articles statistics.
roles:
  - name: knowledge-base-reader
    description: Every signed-in person. Default for all profile roles.
    grants:
      - knowledge-base:article:read
  - name: knowledge-base-author
    description: Support staff who write and maintain articles. Default for the support-staff profile role.
    grants:
      - knowledge-base:article:read
      - knowledge-base:article:read-internal
      - knowledge-base:article:write
      - knowledge-base:stats:read
  - name: knowledge-base-editor
    description: >-
      Reviews and publishes articles and manages categories. Default for the org-admin profile role; an organisation
      can also give it to a support lead.
    grants:
      - knowledge-base:article:read
      - knowledge-base:article:read-internal
      - knowledge-base:article:write
      - knowledge-base:article:publish
      - knowledge-base:category:manage
      - knowledge-base:stats:read
  - name: knowledge-base-viewer
    description: Read-only oversight of all published content and usage. Default for the management profile role.
    grants:
      - knowledge-base:article:read
      - knowledge-base:article:read-internal
      - knowledge-base:stats:read
`,Wl=`# Permission catalogue for sla-management. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: sla-management
permissions:
  - key: sla-management:clock:read
    description: View SLA clocks, breaches, the breaches widget counts, and the calendars and policies behind them.
  - key: sla-management:policy:manage
    description: Create and update business-hours calendars and SLA policies with escalation levels.
roles:
  - name: sla-management-viewer
    description: Sees SLA status of helpdesk tickets. Default for the support-staff and management profile roles.
    grants:
      - sla-management:clock:read
  - name: sla-management-admin
    description: Sets up calendars and policies. Default for org-admin.
    grants:
      - sla-management:clock:read
      - sla-management:policy:manage
`,Yl=`# Permission catalogue for api-gateway. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: api-gateway
permissions: []
#  - key: api-gateway:record:read
#    description: ...
#  - key: api-gateway:record:write
#    description: ...
roles: []
#  - name: api-gateway-admin
#    grants: [api-gateway:record:read, api-gateway:record:write]
`,zl=`# Permission catalogue for audit. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
#
# Reading an audit record means reading what changed, so these are not casual permissions.
# Per ADR-0005, platform:* keys belong to the super admin and are never grantable inside an
# organisation.
module: audit
permissions:
  - key: audit:record:write
    description: >-
      Append a record. Held by modules through packages/sdk, not by people. Writing is not a
      privilege a user can be granted; it is how every module reports what it did.
  - key: audit:record:read
    description: Search and read audit records of this organisation
  - key: audit:record:export
    description: Export this organisation's records for compliance or accreditation
  - key: platform:audit:read
    description: >-
      Super admin only. Read records across every organisation, including platform-level
      actions. Using it is itself recorded.
  - key: platform:audit:redact
    description: >-
      Super admin only. Replace a record's before/after payload with a tombstone under a legal
      erasure request. Never removes the record or the fact of the action.

roles:
  - name: audit-reader
    description: >-
      Reads the organisation's audit trail. Intended for an organisation admin or a governance
      officer, not a general user.
    grants:
      - audit:record:read

  - name: audit-officer
    description: >-
      Governance, IQAC or RTI role that must produce evidence: reads and exports.
    grants:
      - audit:record:read
      - audit:record:export

  - name: org-admin
    description: >-
      The organisation admin reads the organisation's audit trail on their dashboard
      (audit.recent-activity). Same grant as audit-reader.
    grants:
      - audit:record:read
`,Kl=`module: billing
permissions:
  - key: billing:subscription:read
    description: View own plan, trial, usage and invoices.
  - key: billing:subscription:manage
    description: Upgrade, downgrade or cancel own subscription.
  - key: platform:plans:manage
    description: Super admin. Create and edit plans.
  - key: platform:subscriptions:manage
    description: Super admin. Set any organisation's plan, extend trials, comp subscriptions.
  - key: platform:revenue:read
    description: Super admin. Revenue and subscription reports.
roles:
  - name: org-admin
    grants: [billing:subscription:read, billing:subscription:manage]
  - name: super-admin
    grants: [platform:plans:manage, platform:subscriptions:manage, platform:revenue:read]
`,Ql=`# Permission catalogue for documents. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: documents
permissions: []
#  - key: documents:record:read
#    description: ...
#  - key: documents:record:write
#    description: ...
roles: []
#  - name: documents-admin
#    grants: [documents:record:read, documents:record:write]
`,Jl=`# Permission catalogue for event-bus. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
#
# The bus has no end-user surface. These are operator permissions. Per ADR-0005, platform:*
# keys belong to the super admin and are never grantable inside an organisation.
module: event-bus
permissions:
  - key: event-bus:event:read
    description: Inspect events raised by this organisation and their delivery state
  - key: event-bus:event:replay
    description: Replay a dead-lettered event of this organisation
  - key: event-bus:relay:read
    description: >-
      View relay health, backlog and stall state. The backlog counts every organisation's events,
      so only the super admin holds it.
  - key: platform:event-bus:admin
    description: >-
      Super admin only. Inspect and replay events across every organisation, including
      platform-level events that belong to none.

# Blocks are named with platform role ids, the roles a token carries.
roles:
  - name: org-admin
    description: >-
      Diagnoses delivery problems inside their own organisation: seeing an event payload means
      seeing the data that changed, so this is not a general user's grant.
    grants:
      - event-bus:event:read
      - event-bus:event:replay

  # A super admin is handed only the platform: keys that some role grants (eos_core.config.permissions_for).
  - name: super-admin
    description: Super admin. Every organisation's events, platform-level events, and relay health.
    grants:
      - event-bus:event:read
      - event-bus:event:replay
      - event-bus:relay:read
      - platform:event-bus:admin
`,Xl=`# Permission catalogue for identity. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
#
# Authentication routes (login, "who am I") take any active user and need no key.
# Every organisation user also holds the implicit role \`member\`, declared in
# platform/tenancy/contracts/permissions.yaml, which carries what a member needs to open the shell.
module: identity
permissions:
  - key: identity:user:read
    description: List the users of own organisation.
  - key: identity:user:manage
    description: Create, disable and assign roles to users of own organisation. Platform roles cannot be granted.
roles:
  - name: org-admin
    description: Organisation administrator, created at registration. Scoped to one organisation.
    grants: [identity:user:read, identity:user:manage]
`,Zl=`# Permission catalogue for integration-hub. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: integration-hub
permissions: []
#  - key: integration-hub:record:read
#    description: ...
#  - key: integration-hub:record:write
#    description: ...
roles: []
#  - name: integration-hub-admin
#    grants: [integration-hub:record:read, integration-hub:record:write]
`,ed=`# Permission catalogue for notification. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: notification
permissions:
  - key: notification:message:send
    description: >-
      Send a notification over HTTP. Not held by people: modules send in-process through the
      application service, so only the \`service\` block below grants it.
  - key: notification:message:read
    description: >-
      Read this organisation's delivery history. Recipient addresses are masked and bodies are
      never returned, because a message may contain personal data or a token.
  - key: notification:message:resend
    description: Resend a failed or bounced message
  - key: notification:template:read
    description: View notification templates
  - key: notification:template:write
    description: Create and override this organisation's templates
  - key: notification:preference:manage
    description: >-
      Change another user's notification preferences. A person may always change their own
      without this permission.
  - key: platform:notification:read
    description: >-
      Super admin only. Delivery health and failures across every organisation.
  - key: notification:self:read
    description: >-
      Read one's own in-app inbox and one's own notification preferences.
  - key: notification:self:manage
    description: >-
      Mark one's own in-app messages read and change one's own notification preferences. Another
      user's preferences still need notification:preference:manage.

# Each block is named with a platform role id. eos_core.config.permissions_for looks grants up by block name,
# and a token carries the profile role ids (platform/identity/config/profiles), so a block named after this
# module would grant nothing to anyone. Same convention as hostel's \`student\` block and tenancy's catalogue.
roles:
  - name: member
    description: >-
      Implicit. Every active organisation user holds it beside their assigned roles
      (platform/tenancy/contracts/permissions.yaml). Their own inbox and preferences.
    grants:
      - notification:self:read
      - notification:self:manage

  - name: org-admin
    description: >-
      Organisation administrator. Manages the organisation's templates, investigates delivery
      problems and may change another user's preferences.
    grants:
      - notification:message:read
      - notification:message:resend
      - notification:template:read
      - notification:template:write
      - notification:preference:manage

  - name: super-admin
    description: Platform operator. Delivery health across every organisation.
    grants:
      - platform:notification:read

  - name: service
    description: >-
      Not a person. Gives notification:message:send a holder, so the key is not orphaned. No
      profile lists this role, and platform/identity is to refuse it on a user.
    grants:
      - notification:message:send
`,nd=`# Permission catalogue for reporting. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: reporting
permissions: []
#  - key: reporting:record:read
#    description: ...
#  - key: reporting:record:write
#    description: ...
roles: []
#  - name: reporting-admin
#    grants: [reporting:record:read, reporting:record:write]
`,td=`# Permission catalogue for scheduler. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
#
# Job definitions are declared in code and are not editable here, so these permissions cover
# timing and visibility only. Per ADR-0005, platform:* keys belong to the super admin and are
# never grantable inside an organisation.
module: scheduler
permissions:
  - key: scheduler:job:read
    description: View the job definitions modules have declared
  - key: scheduler:schedule:read
    description: View this organisation's schedules and when they next run
  - key: scheduler:schedule:write
    description: >-
      Create, retime, enable, disable or delete a schedule for this organisation. Cannot point
      a schedule at a platform-scoped job.
  - key: scheduler:run:read
    description: View run history and outcomes
  - key: scheduler:run:trigger
    description: >-
      Run a schedule immediately, outside its window. Separate from schedule:write because
      retiming a job and firing it now are different risks.
  - key: platform:scheduler:admin
    description: >-
      Super admin only. Schedule and run platform-scoped jobs such as billing.expire-trials,
      which run once per deployment across every organisation, and see schedules of all
      organisations.

# Blocks are named with platform role ids, the roles a token carries.
roles:
  - name: org-admin
    description: Manages their own academy's scheduled work (organisation-scoped jobs only).
    grants:
      - scheduler:job:read
      - scheduler:schedule:read
      - scheduler:schedule:write
      - scheduler:run:read
      - scheduler:run:trigger

  # A super admin is handed only the platform: keys that some role grants (eos_core.config.permissions_for).
  - name: super-admin
    description: >-
      Super admin. Platform jobs such as billing.expire-trials, every organisation's schedules,
      and the run history ("did the nightly job run?").
    grants:
      - scheduler:job:read
      - scheduler:schedule:read
      - scheduler:schedule:write
      - scheduler:run:read
      - scheduler:run:trigger
      - platform:scheduler:admin
`,sd=`# Permission catalogue for search. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: search
permissions: []
#  - key: search:record:read
#    description: ...
#  - key: search:record:write
#    description: ...
roles: []
#  - name: search-admin
#    grants: [search:record:read, search:record:write]
`,ad=`# Permission catalogue for tenancy. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>. platform:* keys are super-admin only and never grantable inside an organisation.
module: tenancy
permissions:
  - key: tenancy:organisation:read
    description: View own organisation and its entitlement.
  - key: tenancy:organisation:manage
    description: Update own organisation settings and toggle entitled modules.
  - key: platform:organisations:read
    description: Super admin. List and inspect every organisation.
  - key: platform:organisations:manage
    description: Super admin. Activate, suspend, archive organisations.
  - key: platform:entitlements:manage
    description: Super admin. Grant or revoke modules outside the plan.
  - key: platform:organisations:impersonate
    description: Super admin. Start an audited session as an organisation user.
  - key: platform:organisation:export
    description: Super admin. Download everything held about one organisation as JSON (DPDP data export).
  - key: platform:organisation:delete
    description: Super admin. Archive an organisation with a retention period, restore it, or purge its rows for good.
roles:
  - name: member
    description: Implicit. Every active organisation user holds it beside their assigned roles; it is never assigned or removed by hand.
    grants: [tenancy:organisation:read]
  - name: org-admin
    description: Organisation administrator, created at registration. Scoped to one organisation.
    grants: [tenancy:organisation:read, tenancy:organisation:manage]
  - name: super-admin
    description: Platform operator. Outside every organisation.
    grants:
      - platform:organisations:read
      - platform:organisations:manage
      - platform:entitlements:manage
      - platform:organisations:impersonate
      - platform:organisation:export
      - platform:organisation:delete
`,id=`# Permission catalogue for workflow. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: workflow
permissions: []
#  - key: workflow:record:read
#    description: ...
#  - key: workflow:record:write
#    description: ...
roles: []
#  - name: workflow-admin
#    grants: [workflow:record:read, workflow:record:write]
`,rd=Object.assign({"../../../../../integrations/digilocker/module.yaml":Yr,"../../../../../integrations/external-university-portals/module.yaml":zr,"../../../../../integrations/government-portals/module.yaml":Kr,"../../../../../integrations/messaging-providers/module.yaml":Qr,"../../../../../integrations/nad/module.yaml":Jr,"../../../../../integrations/payment-sbiepay/module.yaml":Xr,"../../../../../integrations/video-conferencing/module.yaml":Zr,"../../../../../integrations/wearables/module.yaml":eo,"../../../../../modules/academics/academic-management/module.yaml":no,"../../../../../modules/academics/examinations/module.yaml":to,"../../../../../modules/academics/lms/module.yaml":so,"../../../../../modules/academics/timetable-attendance/module.yaml":ao,"../../../../../modules/campus-life/alumni/module.yaml":io,"../../../../../modules/campus-life/hostel/module.yaml":ro,"../../../../../modules/campus-life/library/module.yaml":oo,"../../../../../modules/campus-life/placement-career/module.yaml":lo,"../../../../../modules/campus-life/transport/module.yaml":co,"../../../../../modules/facilities/asset-management/module.yaml":mo,"../../../../../modules/facilities/facility-booking/module.yaml":po,"../../../../../modules/facilities/inventory-equipment/module.yaml":uo,"../../../../../modules/facilities/maintenance/module.yaml":go,"../../../../../modules/facilities/sports-facilities/module.yaml":ho,"../../../../../modules/finance-operations/budget-grants/module.yaml":fo,"../../../../../modules/finance-operations/e-office/module.yaml":yo,"../../../../../modules/finance-operations/fees-accounts/module.yaml":bo,"../../../../../modules/finance-operations/hr-payroll/module.yaml":xo,"../../../../../modules/finance-operations/procurement/module.yaml":vo,"../../../../../modules/governance/grievance/module.yaml":wo,"../../../../../modules/governance/iqac-accreditation/module.yaml":ko,"../../../../../modules/governance/regulatory-reports/module.yaml":_o,"../../../../../modules/governance/rti/module.yaml":jo,"../../../../../modules/practice/field-training/module.yaml":Fo,"../../../../../modules/practice/portfolio/module.yaml":No,"../../../../../modules/practice/productions/module.yaml":So,"../../../../../modules/practice/projects/module.yaml":Eo,"../../../../../modules/practice/selection-process/module.yaml":Ao,"../../../../../modules/practice/skill-progress/module.yaml":Co,"../../../../../modules/sports/athlete-performance/module.yaml":Po,"../../../../../modules/sports/sports-nutrition-health/module.yaml":Ro,"../../../../../modules/sports/tournament-events/module.yaml":Mo,"../../../../../modules/sports/training-video-analysis/module.yaml":Do,"../../../../../modules/student-lifecycle/admissions/module.yaml":Oo,"../../../../../modules/student-lifecycle/enrolment-registration/module.yaml":To,"../../../../../modules/student-lifecycle/student-information/module.yaml":Bo,"../../../../../modules/student-lifecycle/web-portal-cms/module.yaml":Lo,"../../../../../modules/support/amc-vendor-support/module.yaml":Io,"../../../../../modules/support/helpdesk/module.yaml":qo,"../../../../../modules/support/incident-management/module.yaml":$o,"../../../../../modules/support/knowledge-base/module.yaml":Vo,"../../../../../modules/support/sla-management/module.yaml":Ho,"../../../../../platform/api-gateway/module.yaml":Uo,"../../../../../platform/audit/module.yaml":Go,"../../../../../platform/billing/module.yaml":Wo,"../../../../../platform/documents/module.yaml":Yo,"../../../../../platform/event-bus/module.yaml":zo,"../../../../../platform/identity/module.yaml":Ko,"../../../../../platform/integration-hub/module.yaml":Qo,"../../../../../platform/notification/module.yaml":Jo,"../../../../../platform/reporting/module.yaml":Xo,"../../../../../platform/scheduler/module.yaml":Zo,"../../../../../platform/search/module.yaml":el,"../../../../../platform/tenancy/module.yaml":nl,"../../../../../platform/workflow/module.yaml":tl}),gs=Object.fromEntries(Object.entries(rd).map(([n,t])=>[n.split("/").slice(-2,-1)[0],qt(t)])),od=Object.assign({"../../../../../integrations/messaging-providers/contracts/permissions.yaml":sl,"../../../../../integrations/payment-sbiepay/contracts/permissions.yaml":al,"../../../../../modules/academics/academic-management/contracts/permissions.yaml":il,"../../../../../modules/academics/examinations/contracts/permissions.yaml":rl,"../../../../../modules/academics/lms/contracts/permissions.yaml":ol,"../../../../../modules/academics/timetable-attendance/contracts/permissions.yaml":ll,"../../../../../modules/campus-life/alumni/contracts/permissions.yaml":dl,"../../../../../modules/campus-life/hostel/contracts/permissions.yaml":cl,"../../../../../modules/campus-life/library/contracts/permissions.yaml":ml,"../../../../../modules/campus-life/placement-career/contracts/permissions.yaml":pl,"../../../../../modules/campus-life/transport/contracts/permissions.yaml":ul,"../../../../../modules/facilities/asset-management/contracts/permissions.yaml":gl,"../../../../../modules/facilities/facility-booking/contracts/permissions.yaml":hl,"../../../../../modules/facilities/inventory-equipment/contracts/permissions.yaml":fl,"../../../../../modules/facilities/maintenance/contracts/permissions.yaml":yl,"../../../../../modules/facilities/sports-facilities/contracts/permissions.yaml":bl,"../../../../../modules/finance-operations/budget-grants/contracts/permissions.yaml":xl,"../../../../../modules/finance-operations/e-office/contracts/permissions.yaml":vl,"../../../../../modules/finance-operations/fees-accounts/contracts/permissions.yaml":wl,"../../../../../modules/finance-operations/hr-payroll/contracts/permissions.yaml":kl,"../../../../../modules/finance-operations/procurement/contracts/permissions.yaml":_l,"../../../../../modules/governance/grievance/contracts/permissions.yaml":jl,"../../../../../modules/governance/iqac-accreditation/contracts/permissions.yaml":Fl,"../../../../../modules/governance/regulatory-reports/contracts/permissions.yaml":Nl,"../../../../../modules/governance/rti/contracts/permissions.yaml":Sl,"../../../../../modules/practice/field-training/contracts/permissions.yaml":El,"../../../../../modules/practice/portfolio/contracts/permissions.yaml":Al,"../../../../../modules/practice/productions/contracts/permissions.yaml":Cl,"../../../../../modules/practice/projects/contracts/permissions.yaml":Pl,"../../../../../modules/practice/selection-process/contracts/permissions.yaml":Rl,"../../../../../modules/practice/skill-progress/contracts/permissions.yaml":Ml,"../../../../../modules/sports/athlete-performance/contracts/permissions.yaml":Dl,"../../../../../modules/sports/sports-nutrition-health/contracts/permissions.yaml":Ol,"../../../../../modules/sports/tournament-events/contracts/permissions.yaml":Tl,"../../../../../modules/sports/training-video-analysis/contracts/permissions.yaml":Bl,"../../../../../modules/student-lifecycle/admissions/contracts/permissions.yaml":Ll,"../../../../../modules/student-lifecycle/enrolment-registration/contracts/permissions.yaml":Il,"../../../../../modules/student-lifecycle/student-information/contracts/permissions.yaml":ql,"../../../../../modules/student-lifecycle/web-portal-cms/contracts/permissions.yaml":$l,"../../../../../modules/support/amc-vendor-support/contracts/permissions.yaml":Vl,"../../../../../modules/support/helpdesk/contracts/permissions.yaml":Hl,"../../../../../modules/support/incident-management/contracts/permissions.yaml":Ul,"../../../../../modules/support/knowledge-base/contracts/permissions.yaml":Gl,"../../../../../modules/support/sla-management/contracts/permissions.yaml":Wl,"../../../../../platform/api-gateway/contracts/permissions.yaml":Yl,"../../../../../platform/audit/contracts/permissions.yaml":zl,"../../../../../platform/billing/contracts/permissions.yaml":Kl,"../../../../../platform/documents/contracts/permissions.yaml":Ql,"../../../../../platform/event-bus/contracts/permissions.yaml":Jl,"../../../../../platform/identity/contracts/permissions.yaml":Xl,"../../../../../platform/integration-hub/contracts/permissions.yaml":Zl,"../../../../../platform/notification/contracts/permissions.yaml":ed,"../../../../../platform/reporting/contracts/permissions.yaml":nd,"../../../../../platform/scheduler/contracts/permissions.yaml":td,"../../../../../platform/search/contracts/permissions.yaml":sd,"../../../../../platform/tenancy/contracts/permissions.yaml":ad,"../../../../../platform/workflow/contracts/permissions.yaml":id}),an={},Ce={};var It;for(const[n,t]of Object.entries(od)){const s=n.split("/").slice(-3,-2)[0],i=qt(t)??{};an[s]=i.permissions??[];for(const a of i.roles??[]){const o=Ce[It=a.name]??(Ce[It]=new Set);for(const m of a.grants??[])o.add(m)}}function Qn(n,t=!1){const s=new Set;for(const i of n)for(const a of Ce[i]??[])s.add(a);if(t)for(const i of Object.values(Ce))for(const a of i)a.startsWith("platform:")&&s.add(a);return[...s].sort()}const Re=sa(),Hn=aa(),gn=ia();function Qe(n){const t=s=>s.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");return n.title.split(" / ").find(s=>t(s)===n.profile)??n.title}const ld="sports-college",hn=Re[ld],dd=new Set(["identity","tenancy","billing"]);function Jn(n,t,s,i,a){const o=gs[n];return{id:n,name:t,kind:s,suiteId:i,description:(o==null?void 0:o.description)??"",status:(o==null?void 0:o.status)??"planned",tier:(o==null?void 0:o.tier)??"",field:o==null?void 0:o.field,implemented:dd.has(n),route:a}}const cd=(n,t,s,i)=>Jn(t,s,"feature",n,i),he=(n,t,s,i,a)=>({id:n,letter:t,diagram:s,name:i,domain:n,color:"#7E22CE",modules:a.map(([o,m,p])=>cd(n,o,m,p))}),Ne=[he("student-lifecycle","A","Suite A","Pre-Admission & Student Information",[["web-portal-cms","Web Portal & CMS"],["admissions","Admission & Application","/admissions"],["student-information","Student Information (SIS)"],["enrolment-registration","Enrolment & Registration"]]),he("academics","B","Suite B","Academic & Learning Management",[["academic-management","Academic Management"],["lms","Learning Management (LMS)"],["examinations","Examination Management"],["timetable-attendance","Timetable & Attendance"]]),he("practice","",void 0,"Practice",[["portfolio","Portfolio"],["projects","Projects"],["selection-process","Selection Process"],["productions","Productions"],["field-training","Field Training"],["skill-progress","Skill Progress"]]),he("sports","C","Suite C","Sports & Athlete Performance",[["athlete-performance","Athlete Performance"],["training-video-analysis","Training & Video Analysis"],["sports-nutrition-health","Sports Nutrition & Health"],["tournament-events","Tournament & Events"]]),he("facilities","D","Suite D","Facility & Resource Management",[["sports-facilities","Sports Facilities"],["facility-booking","Facility Booking"],["inventory-equipment","Inventory & Equipment"],["asset-management","Asset Management"],["maintenance","Maintenance"]]),he("finance-operations","E","Suite E","Finance & Institutional Operations",[["fees-accounts","Fees & Accounts"],["budget-grants","Budget & Grants"],["procurement","Procurement"],["hr-payroll","HR & Payroll"],["e-office","E-Office & Files"]]),he("campus-life","F","Suite F","Campus Life & Student Services",[["hostel","Hostel Management"],["transport","Transport Management"],["library","Library Management"],["placement-career","Placement & Career"],["alumni","Alumni Management"]]),he("governance","G","Suite G","Governance, Grievance & Compliance",[["grievance","Grievance (SGRC / POSH)"],["rti","RTI Management"],["iqac-accreditation","IQAC / Accreditation"],["regulatory-reports","Regulatory Reports"]]),he("support","•","Global","Global Support Systems",[["helpdesk","Helpdesk & Ticketing"],["sla-management","SLA Management"],["knowledge-base","Knowledge Base"],["incident-management","Incident & Problem"],["amc-vendor-support","User Support & AMC"]])],Sn=n=>n.diagram?`${n.diagram} · ${n.name}`:n.name,se=(n,t,s)=>Jn(n,t,"platform","platform",s),Te=[se("identity","Identity & Access","/users"),se("tenancy","Tenancy"),se("billing","Billing"),se("workflow","Workflow & Approvals"),se("audit","Audit Log","/audit-logs"),se("notification","Notifications"),se("documents","Documents & Media"),se("reporting","Reporting & Analytics"),se("search","Global Search"),se("scheduler","Scheduler"),se("event-bus","Event Bus"),se("integration-hub","Integration Hub"),se("api-gateway","API Gateway")],ke=(n,t)=>Jn(n,t,"integration","integrations"),He=[ke("payment-sbiepay","SBIePay"),ke("digilocker","DigiLocker"),ke("nad","NAD"),ke("government-portals","Government Systems"),ke("messaging-providers","Email / SMS / WhatsApp"),ke("video-conferencing","Video Conferencing"),ke("wearables","Wearable Devices"),ke("external-university-portals","Other University Portals")],Xn=[...Ne.flatMap(n=>n.modules),...Te,...He],md=new Map(Xn.map(n=>[n.id,n])),Je=n=>md.get(n),En=n=>Ne.find(t=>t.id===n),pd=n=>{const t=En(n.suiteId);return t?`${t.domain}/${n.id}`:n.id},hs=n=>{var t;return((t=En(n.suiteId))==null?void 0:t.color)??"#7E22CE"},fs=n=>n.route??`/modules/${n.id}`,ud=[{icon:Me,title:"Multi-tenant",text:"One deployment, many organisations. Each signs in to its own data."},{icon:ns,title:"Academy profiles",text:`${Object.keys(Re).length} academy types, each with its own suites, roles and dashboards.`},{icon:cs,title:"Plans & entitlements",text:"Trial, standard and premium plans decide which modules are on."},{icon:Pe,title:"Permission keys",text:"Every module checks keys, never roles, and records changes to audit."}],gd=[{value:Object.keys(Re).length,label:"Academy types"},{value:Ne.reduce((n,t)=>n+t.modules.length,0),label:"Feature modules"},{value:Te.length,label:"Platform services"}],hd=()=>{const n=Fn(),{preview:t,signIn:s}=me(),[i,a]=f.useState(t?"admin@example.org":""),[o,m]=f.useState(t?"••••••••••••":""),[p,g]=f.useState(!1),[u,k]=f.useState(null),h=async l=>{l.preventDefault(),g(!0),k(null);try{await s(i.trim(),o),n("/dashboard",{replace:!0})}catch(y){k(ii(y)),g(!1)}};return e.jsxs("div",{className:"min-h-screen bg-[#F6F8FB] grid grid-cols-1 lg:grid-cols-2",children:[e.jsxs("aside",{className:"relative hidden lg:flex flex-col justify-between overflow-hidden text-white",style:{padding:40},"aria-label":"About Education OS",children:[e.jsx("div",{className:"absolute inset-0 bg-cover",style:{backgroundImage:`url('${B("/campus.jpg")}')`,backgroundPosition:"62% 72%"},"aria-hidden":!0}),e.jsx("div",{className:"absolute inset-0",style:{backgroundImage:"var(--hero-gradient)",opacity:.9},"aria-hidden":!0}),e.jsx("div",{className:"absolute inset-0 pointer-events-none",style:{backgroundImage:"radial-gradient(rgba(255,255,255,0.18) 1px, transparent 1px)",backgroundSize:"22px 22px"},"aria-hidden":!0}),e.jsx("div",{className:"absolute rounded-full pointer-events-none",style:{width:420,height:420,right:-140,top:-120,background:"radial-gradient(circle, rgba(246,91,102,0.45), transparent 70%)"},"aria-hidden":!0}),e.jsxs("div",{className:"relative z-10 flex items-center gap-3",children:[e.jsx("span",{className:"rounded-xl bg-white flex items-center justify-center shadow-lg",style:{width:48,height:48},children:e.jsx(ps,{size:36})}),e.jsx(us,{inverse:!0,className:"text-2xl"})]}),e.jsxs("div",{className:"relative z-10 max-w-md space-y-6 eos-nav-in",children:[e.jsxs("div",{children:[e.jsx("h1",{className:"text-[32px] leading-tight font-bold tracking-[-0.02em]",children:"One platform for every institution"}),e.jsx("p",{className:"eos-hero-sub text-[14px] mt-2",children:"Configured for the way each institution teaches, trains, manages and supports its students."})]}),e.jsx("ul",{className:"space-y-3 stagger",children:ud.map(({icon:l,title:y,text:v})=>e.jsxs("li",{className:"flex items-start gap-3",children:[e.jsx("span",{className:"w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0",style:{background:"rgba(255,255,255,0.16)"},children:e.jsx(l,{className:"w-4 h-4"})}),e.jsxs("div",{children:[e.jsx("p",{className:"text-sm font-semibold",children:y}),e.jsx("p",{className:"eos-hero-sub text-xs",children:v})]})]},y))})]}),e.jsxs("div",{className:"relative z-10 space-y-4",children:[e.jsx("div",{className:"grid grid-cols-3 gap-3",children:gd.map(l=>e.jsxs("div",{className:"rounded-xl p-3",style:{background:"rgba(255,255,255,0.12)",boxShadow:"inset 0 0 0 1px rgba(255,255,255,0.22)"},children:[e.jsx("div",{className:"text-2xl font-bold tabular-nums",children:l.value}),e.jsx("div",{className:"eos-hero-sub text-[11px]",children:l.label})]},l.label))}),e.jsx("p",{className:"eos-hero-sub text-[11px]",children:"© 2026 Education OS · Multi-tenant platform for higher-education institutions"})]})]}),e.jsxs("main",{className:"relative flex flex-col justify-center py-12 px-4 sm:px-8 overflow-hidden",children:[e.jsx("div",{className:"absolute inset-0 opacity-[0.03] pointer-events-none",style:{backgroundImage:"radial-gradient(#7E22CE 1px, transparent 1px)",backgroundSize:"24px 24px"},"aria-hidden":!0}),e.jsx("div",{className:"absolute rounded-full pointer-events-none",style:{width:360,height:360,left:-160,bottom:-160,background:"radial-gradient(circle, rgba(124,58,237,0.12), transparent 70%)"},"aria-hidden":!0}),e.jsxs("div",{className:"relative z-10 w-full max-w-md mx-auto page-enter",children:[e.jsxs("div",{className:"text-center",children:[e.jsx("img",{src:B("/eos-logo.png"),alt:"Education OS — University Operating System",className:"mx-auto w-full h-auto",style:{maxWidth:260}}),e.jsx("p",{className:"mt-3 text-xs text-[#475569] font-medium uppercase tracking-wider",children:"One configurable higher-education platform"})]}),e.jsxs("div",{className:"mt-6 bg-[#FFFFFF] py-8 px-6 sm:px-10 shadow-lg rounded-xl border border-[#E2E8F0]",children:[e.jsxs("div",{className:"flex items-center justify-between pb-4 border-b border-[#E2E8F0] mb-6",children:[e.jsxs("div",{children:[e.jsx("span",{className:"text-sm font-semibold text-[#12233F]",children:"Sign In to Portal"}),e.jsx("p",{className:"text-xs text-[#475569]",children:"Super admins and organisation admins"})]}),t?e.jsxs("span",{className:"inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#F39A1926] text-[#8A4F00]",children:[e.jsx(be,{className:"w-3.5 h-3.5"}),"Preview mode"]}):e.jsxs("span",{className:"inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#16834B26] text-[#126B3D]",children:[e.jsx(ze,{className:"w-3.5 h-3.5"}),"Connected to API"]})]}),e.jsxs("form",{className:"space-y-4",onSubmit:h,children:[e.jsxs("div",{children:[e.jsx("label",{className:"block text-xs font-semibold text-[#12233F] mb-1.5",children:"Institutional Email"}),e.jsxs("div",{className:"relative rounded-lg shadow-2xs",children:[e.jsx("div",{className:"absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#475569]",children:e.jsx(ls,{className:"h-4 w-4"})}),e.jsx("input",{type:"email",required:!0,value:i,onChange:l=>a(l.target.value),placeholder:"e.g. name@your-institution.edu",className:"block w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]"})]})]}),e.jsxs("div",{children:[e.jsxs("div",{className:"flex items-center justify-between mb-1.5",children:[e.jsx("label",{className:"block text-xs font-semibold text-[#12233F]",children:"Password"}),e.jsx("a",{href:"#forgot",onClick:l=>{l.preventDefault(),alert("Password reset is not available yet. Ask your organisation admin.")},className:"text-xs font-medium text-[#7E22CE] hover:underline",children:"Forgot Password?"})]}),e.jsxs("div",{className:"relative rounded-lg shadow-2xs",children:[e.jsx("div",{className:"absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#475569]",children:e.jsx(ts,{className:"h-4 w-4"})}),e.jsx("input",{type:"password",required:!0,value:o,onChange:l=>m(l.target.value),placeholder:"••••••••••••",className:"block w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]"})]})]}),u&&e.jsx("p",{role:"alert",className:"rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]",children:u}),e.jsx("div",{className:"pt-1",children:e.jsx("button",{type:"submit",disabled:p,className:"w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-xs font-semibold text-white bg-[#F65B66] hover:bg-[#E9505C] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#7E22CE] transition-all shadow-md active:scale-[0.99] disabled:opacity-70",children:p?e.jsxs("span",{className:"inline-flex items-center gap-2",children:[e.jsx("span",{className:"w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"}),"Signing in..."]}):e.jsxs(e.Fragment,{children:[e.jsx("span",{children:"Sign In to Education OS"}),e.jsx(Fe,{className:"w-4 h-4"})]})})})]}),t&&e.jsxs("div",{className:"mt-6 pt-5 border-t border-[#E2E8F0]",children:[e.jsx("p",{className:"text-[11px] font-semibold text-[#475569] uppercase tracking-wider mb-2 text-center",children:"Quick Prototype Demo Logins"}),e.jsx("button",{type:"button",onClick:()=>{a("admin@example.org"),m("demo")},className:"w-full px-2 py-1.5 text-[11px] font-medium rounded-md bg-[#7E22CE26] text-[#7E22CE] hover:bg-[#7E22CE40] transition-colors text-center border border-[#9333EA]/20",children:"Preview as organisation admin (sample data)"})]}),e.jsxs("div",{className:"mt-6 flex items-center justify-center gap-2 text-[11px] text-[#475569]",children:[e.jsx(be,{className:"w-3.5 h-3.5 text-[#126B3D]"}),e.jsx("span",{children:"Each organisation sees only its own data (row-level security)"})]})]}),e.jsxs("div",{className:"mt-6 text-center text-xs text-[#475569] space-y-1 lg:hidden",children:[e.jsx("p",{children:"Education OS"}),e.jsx("p",{className:"text-[11px] text-[#64748B]",children:"Multi-tenant platform for higher-education institutions"})]})]})]})]})},ys={"web-portal-cms":gr,admissions:Ye,"student-information":sn,"enrolment-registration":rr,"academic-management":Yn,lms:_r,examinations:tn,"timetable-attendance":sr,"athlete-performance":Ke,"training-video-analysis":Br,"sports-nutrition-health":Qi,"tournament-events":vr,"sports-facilities":cr,"facility-booking":ar,"inventory-equipment":Jt,"asset-management":jr,maintenance:Lr,"fees-accounts":lr,"budget-grants":Fr,procurement:Cr,"hr-payroll":er,"e-office":ur,hostel:es,transport:tr,library:xr,"placement-career":Me,alumni:Tr,grievance:rs,rti:pr,"iqac-accreditation":Xi,"regulatory-reports":Ar,helpdesk:Nn,"sla-management":Rr,"knowledge-base":Zi,"incident-management":Pr,"amc-vendor-support":hr},fd="trial";function Se(){const{preview:n,session:t}=me();return f.useMemo(()=>{var s;if(t!=null&&t.entitlement)return{source:"organisation",profile:Re[t.entitlement.academyType]??null,planTitle:((s=Hn[t.entitlement.plan])==null?void 0:s.title)??t.entitlement.plan,entitlement:t.entitlement};if(n||!t){const i=Hn[fd];return{source:"preview",profile:hn,planTitle:i.title,entitlement:ra(hn,i)}}return{source:"platform",profile:null,planTitle:null,entitlement:null}},[n,t])}function Ie(n,t){var i;if(n.kind==="platform")return"platform";if(!t.entitlement||!t.profile)return"per-organisation";if(n.kind==="integration"){if(!(t.profile.integrations??[]).includes(n.id))return"not-in-profile";const a=((i=Hn[t.entitlement.plan])==null?void 0:i.integrations)??[];return a.includes("*")||a.includes(n.id)?"included":"upgrade"}const s=pd(n);return t.entitlement.modules.has(s)?"included":t.profile.modules.includes(s)?"upgrade":"not-in-profile"}const fn={included:"Included in plan",upgrade:"Upgrade to unlock","not-in-profile":"Not in academy profile",platform:"Platform service","per-organisation":"Per organisation"},yd=(n,t)=>{const s=Ie(n,t);return n.implemented&&(s==="included"||s==="platform")};function Zn(){const{preview:n,session:t}=me(),s=Se(),i=s.profile?Qe(s.profile):void 0,a=s.planTitle?`${s.planTitle} plan`:void 0;return t!=null&&t.organisation?{name:t.organisation.name,detail:[i,a].filter(Boolean).join(" · "),connected:!0}:t!=null&&t.me.is_super_admin?{name:"Education OS platform",detail:"Super admin · all organisations",connected:!0}:{name:`Demo ${i??"organisation"}`,detail:[a,"preview"].filter(Boolean).join(" · "),connected:!n}}const bd={"student-lifecycle":"Student Lifecycle",academics:"Academics",practice:"Practice",sports:"Sports",facilities:"Facilities","finance-operations":"Finance & Operations","campus-life":"Campus Life",governance:"Governance",support:"Global Support"},xd={"student-lifecycle":Ye,academics:Yn,practice:is,sports:Ke,facilities:Me,"finance-operations":cs,"campus-life":es,governance:Kn,support:Nn},vd={"student-lifecycle":[["admissions","Admissions"],["student-information","Students"],["enrolment-registration","Enrolment & Registration"],["web-portal-cms","Web Portal & CMS"]],academics:[["academic-management","Academic Management"],["lms","Learning (LMS)"],["examinations","Examination"],["timetable-attendance","Attendance & Timetable"]],sports:[["athlete-performance","Athletes"],["training-video-analysis","Training & Video"],["sports-nutrition-health","Nutrition & Health"],["tournament-events","Tournaments"]],facilities:[["sports-facilities","Facilities"],["facility-booking","Bookings"],["inventory-equipment","Inventory"],["asset-management","Assets"],["maintenance","Maintenance"]],"finance-operations":[["fees-accounts","Fees & Payments"],["budget-grants","Budget & Grants"],["procurement","Procurement"],["hr-payroll","HR & Payroll"],["e-office","E-Office"]],"campus-life":[["hostel","Hostel"],["transport","Transport"],["library","Library"],["placement-career","Placement & Career"],["alumni","Alumni"]],governance:[["grievance","Grievance"],["rti","RTI"],["iqac-accreditation","IQAC / Accreditation"],["regulatory-reports","Compliance & Reports"]],support:[["helpdesk","Helpdesk"],["sla-management","SLA Management"],["knowledge-base","Knowledge Base"],["incident-management","Incidents"],["amc-vendor-support","AMC & Vendors"]]},ht={},wd="bg-[#FEF2F2] text-[#B91C1C]",bs={name:"Dashboard",path:"/dashboard",icon:br,live:!0},xs=[{name:"Users",path:"/users",icon:ds,live:!0},{name:"Roles & Permissions",path:"/roles",icon:ze,live:!0},{name:"Role Dashboards",path:"/dashboards",icon:Le,live:!0},{name:"Module Registry",path:"/modules",icon:pn,live:!0},{name:"Audit Log",path:"/audit-logs",icon:Zt,live:!0}],kd=n=>Ne.map(t=>{const s=vd[t.id]??t.modules.map(i=>[i.id,i.name]);return{id:t.id,title:`${t.letter&&t.letter!=="•"?`${t.letter} · `:""}${bd[t.id]??t.name}`,icon:xd[t.id]??pn,items:s.flatMap(([i,a])=>{var m,p;const o=t.modules.find(g=>g.id===i);return o?[{name:a,path:fs(o),icon:ys[o.id]??pn,badge:(m=ht[o.id])==null?void 0:m.value,badgeColor:(p=ht[o.id])==null?void 0:p.color,live:yd(o,n)}]:[]})}}),_d=n=>n.items.reduce((t,s)=>t+(s.badgeColor===wd&&Number(s.badge)||0),0),Un=(n,t)=>n===t||t!=="/dashboard"&&t!=="/modules"&&n.startsWith(`${t}/`),jd=(n,t)=>{const s=n.find(a=>a.items.some(o=>Un(t,o.path)));if(s)return s.id;const i=[bs,...xs].find(a=>Un(t,a.path));return i?i.path:t.startsWith("/modules/")?"/modules":void 0},Fd={"student-lifecycle":{c:"#3B82F6",t:"#EFF6FF",at:"#1D4ED8"},academics:{c:"#7C3AED",t:"#F5F3FF",at:"#6D28D9"},sports:{c:"#059669",t:"#ECFDF5",at:"#047857"},facilities:{c:"#D97706",t:"#FFFBEB",at:"#B45309"},"finance-operations":{c:"#0F9F8A",t:"#F0FDFA",at:"#0F766E"},"campus-life":{c:"#E45A8A",t:"#FFF1F5",at:"#BE185D"},governance:{c:"#C026D3",t:"#FDF4FF",at:"#A21CAF"},support:{c:"#64748B",t:"#F1F5F9",at:"#334155"}},ft={c:"#4338CA",t:"#EEF2FF",ic:"#A9B3D6",h:"#F1F5F9",at:"#4338CA"},yt=n=>({"--c":n.c,"--t":n.t,"--ic":n.ic??n.c,"--h":n.h??n.t,"--at":n.at??"#12233F"}),bt=n=>`group relative w-full flex items-center gap-2.5 px-2.5 h-[34px] rounded-lg text-left text-[13px] transition-colors duration-200 ${n?"bg-[var(--t)] text-[var(--at)] font-semibold":"text-[#12233F] font-medium hover:bg-[var(--h)]"}`,xt=n=>n?"text-[var(--c)]":"text-[var(--ic)] group-hover:text-[var(--c)] group-hover:brightness-90",vt=()=>e.jsx("span",{"aria-hidden":!0,className:"eos-bar-in absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-[var(--c)]"}),wt=n=>`transition-transform duration-200 group-hover:scale-105 ${n?"eos-pop":""}`,kt=({children:n,collapsed:t})=>t?e.jsx("div",{className:"mx-3 my-3 border-t border-[#EEF2F6]"}):e.jsx("div",{className:"px-3 pt-5 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#94A3B8]",children:n}),Nd=({collapsed:n,onToggleCollapse:t,mobileOpen:s,onCloseMobile:i})=>{const a=$e(),o=Se(),m=Zn(),p=kd(o),g=jd(p,a.pathname),[u,k]=f.useState(()=>g?{[g]:!0}:{});f.useEffect(()=>{g&&k(l=>l[g]?l:{...l,[g]:!0})},[g]);const h=l=>{const y=g===l.path,v=l.icon;return e.jsxs(ct,{to:l.path,onClick:i,title:n?l.name:void 0,"aria-current":y?"page":void 0,style:yt(ft),className:`${bt(y)} ${n?"justify-center px-0":""}`,children:[y&&e.jsx(vt,{}),e.jsx(v,{className:`w-[18px] h-[18px] flex-shrink-0 ${wt(y)} ${xt(y)}`}),!n&&e.jsx("span",{className:"truncate flex-1",children:l.name})]},l.path)};return e.jsxs(e.Fragment,{children:[s&&e.jsx("div",{className:"fixed inset-0 bg-black/30 backdrop-blur-xs z-40 lg:hidden",onClick:i}),e.jsxs("aside",{className:`fixed top-0 bottom-0 left-0 z-50 flex flex-col eos-sidebar-bg text-[#12233F] border-r border-[#ECE6F7] transition-all duration-300 ease-in-out
          ${n?"w-[72px]":"w-[260px]"}
          ${s?"translate-x-0":"-translate-x-full lg:translate-x-0"}
        `,children:[e.jsxs("div",{className:`mx-3 mt-3 mb-2 flex items-center rounded-xl border border-[#E6ECF5] bg-[linear-gradient(135deg,#F2F7FF_0%,#FFFFFF_55%,#F1FAF4_100%)] ${n?"flex-col gap-2 px-1.5 py-2.5":"justify-between gap-2 px-2.5 py-2.5"}`,children:[e.jsxs("div",{className:"group min-w-0 flex items-center gap-2",title:"Education OS",children:[e.jsx("span",{className:"transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:scale-105",children:e.jsx(ps,{size:38})}),!n&&e.jsx("h1",{children:e.jsx(us,{className:"text-[17px]"})})]}),e.jsx("button",{onClick:t,className:"hidden lg:flex items-center justify-center w-7 h-7 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-white/70 transition-colors flex-shrink-0",title:n?"Expand sidebar":"Collapse sidebar",children:n?e.jsx(Xt,{className:"w-4 h-4"}):e.jsx(ir,{className:"w-4 h-4"})})]}),e.jsxs("nav",{className:"flex-1 overflow-y-auto px-3 pb-4 eos-on-dark","aria-label":"Main",children:[e.jsx("div",{className:"pt-1",children:h(bs)}),e.jsx(kt,{collapsed:n,children:"Education OS"}),e.jsx("div",{className:"space-y-0.5",children:p.map((l,y)=>{const v=g===l.id,x=!!u[l.id]&&!n,F=l.icon,E=_d(l),A=Fd[l.id]??ft;return e.jsxs("div",{className:"eos-nav-in",style:{...yt(A),animationDelay:`${60+y*40}ms`},children:[e.jsxs("button",{onClick:()=>{n&&t(),k(b=>({...b,[l.id]:n?!0:!b[l.id]}))},"aria-expanded":x,"aria-current":v?"location":void 0,title:n?l.title:void 0,className:`${bt(v)} ${n?"justify-center px-0":""}`,children:[v&&e.jsx(vt,{}),e.jsx(F,{className:`w-[18px] h-[18px] flex-shrink-0 ${wt(v)} ${xt(v)}`}),!n&&e.jsxs(e.Fragment,{children:[e.jsx("span",{className:"truncate flex-1",children:l.title}),!x&&E>0&&e.jsxs("span",{title:`${E} urgent`,"aria-label":`${E} urgent`,className:"relative flex w-1.5 h-1.5 flex-shrink-0",children:[e.jsx("span",{className:"absolute inline-flex h-full w-full rounded-full bg-[#DC2626] opacity-60 animate-ping"}),e.jsx("span",{className:"relative inline-flex w-1.5 h-1.5 rounded-full bg-[#DC2626]"})]}),e.jsx(en,{className:`w-4 h-4 flex-shrink-0 transition-transform duration-300 text-[var(--c)] ${v?"opacity-100":"opacity-50 group-hover:opacity-90"} ${x?"":"-rotate-90"}`})]})]}),e.jsx("div",{className:`grid transition-[grid-template-rows,opacity] duration-300 ease-out ${x?"grid-rows-[1fr] opacity-100":"grid-rows-[0fr] opacity-0"}`,...x?{}:{inert:""},children:e.jsx("div",{className:"overflow-hidden",children:e.jsx("div",{className:"ml-[19px] pl-3 border-l border-[#E2E8F0] py-1 space-y-0.5",children:l.items.map(b=>{const _=Un(a.pathname,b.path);return e.jsxs(ct,{to:b.path,onClick:i,className:`relative flex items-center gap-2 px-2.5 h-8 rounded-md text-[13px] hover:text-[#12233F] hover:bg-[#F8FAFC] hover:translate-x-1 transition-all duration-200 ${_?"text-[#0B1730]":"text-[#475569]"}`,children:[_&&e.jsx("span",{"aria-hidden":!0,className:"absolute left-[3px] top-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-[var(--c)]"}),e.jsx("span",{className:"truncate flex-1",children:b.name}),b.badge!==void 0&&e.jsx("span",{className:`text-[10px] font-semibold min-w-[20px] text-center px-1.5 py-0.5 rounded-md flex-shrink-0 ${b.badgeColor??"bg-[#F3E8FF] text-[#7E22CE]"}`,children:b.badge})]},b.path)})})})})]},l.id)})}),e.jsx(kt,{collapsed:n,children:"Administration"}),e.jsx("div",{className:"space-y-0.5 eos-nav-in",style:{animationDelay:"420ms"},children:xs.map(h)})]}),e.jsx("div",{className:"px-4 py-3 border-t border-[#E2E8F0] eos-on-dark",children:n?e.jsx("div",{className:"flex justify-center",title:m.connected?"Connected to the API":"Preview",children:e.jsx("span",{className:`w-2 h-2 rounded-full ${m.connected?"bg-[#16834B] animate-pulse":"bg-[#94A3B8]"}`})}):e.jsxs("div",{className:"flex items-center gap-2.5",children:[e.jsx("span",{className:"flex-shrink-0 w-8 h-8 rounded-lg bg-[#EEF2FF] text-[#3730A3] flex items-center justify-center",children:e.jsx(yr,{className:"w-4 h-4"})}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsxs("div",{className:"flex items-center justify-between gap-2",children:[e.jsx("p",{className:"text-[12px] font-semibold text-[#12233F] truncate",children:m.name}),m.connected?e.jsxs("span",{className:"inline-flex items-center gap-1.5 text-[10.5px] font-medium text-[#126B3D] whitespace-nowrap",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-[#16834B] animate-pulse"}),"Connected"]}):e.jsxs("span",{className:"inline-flex items-center gap-1.5 text-[10.5px] font-medium text-[#64748B] whitespace-nowrap",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-[#94A3B8]"}),"Preview"]})]}),e.jsx("p",{className:"text-[11px] text-[#64748B] truncate",children:m.detail})]})]})})]})]})},Sd=[{id:"USR-1001",name:"Dr. A. Sharma",email:"a.sharma@example.edu",role:"org-admin",department:"Central Administration",status:"Active",lastLogin:"Today, 09:40 AM",dataScope:"Institution",employeeId:"ADM-2018-001",phone:"+91 98140 23891",twoFactorEnabled:!0},{id:"USR-1002",name:"P. Singh, CA",email:"p.singh@example.edu",role:"finance-staff",department:"Finance & Accounts",status:"Active",lastLogin:"Today, 10:42 AM",dataScope:"Department",employeeId:"FIN-2019-014",phone:"+91 98722 84910",twoFactorEnabled:!0},{id:"USR-1003",name:"Dr. R. Kaur",email:"r.kaur@example.edu",role:"faculty",department:"Computer Science & AI",status:"Active",lastLogin:"Yesterday, 04:15 PM",dataScope:"Assigned Records",employeeId:"FAC-2020-045",phone:"+91 94178 30129",twoFactorEnabled:!0},{id:"USR-1004",name:"Col. Gurmeet Dhillon (Retd.)",email:"g.dhillon@example.edu",role:"department-admin",department:"Sports Science & Athletics",status:"Active",lastLogin:"Today, 10:04 AM",dataScope:"Department",employeeId:"SPT-2019-003",phone:"+91 98150 99421",twoFactorEnabled:!0},{id:"USR-1005",name:"Dr. Vikram Malhotra",email:"v.malhotra@example.edu",role:"examination-staff",department:"Controller of Examinations",status:"Active",lastLogin:"Today, 10:35 AM",dataScope:"Institution",employeeId:"EXM-2021-008",phone:"+91 98881 77312",twoFactorEnabled:!0},{id:"USR-1006",name:"Rajinder Kumar",email:"r.kumar@example.edu",role:"coach",department:"Athletics & Track",status:"Active",lastLogin:"Yesterday, 06:20 PM",dataScope:"Assigned Records",employeeId:"CCH-2022-019",phone:"+91 97790 41203",twoFactorEnabled:!1},{id:"USR-1007",name:"Manpreet Sandhu",email:"m.sandhu@example.edu",role:"department-admin",department:"Physical Education",status:"Pending",lastLogin:"04 Oct 2026, 11:10 AM",dataScope:"Department",employeeId:"DPA-2024-032",phone:"+91 98144 55928",twoFactorEnabled:!1},{id:"USR-1008",name:"Sunita Verma",email:"s.verma@example.edu",role:"support-staff",department:"Student Support Center",status:"Active",lastLogin:"Today, 08:30 AM",dataScope:"Assigned Records",employeeId:"HLP-2023-011",phone:"+91 99148 66201",twoFactorEnabled:!0},{id:"USR-1009",name:"Harbhajan Chahal",email:"h.chahal@example.gov",role:"governance",department:"State Internal Audit Bureau",status:"Suspended",lastLogin:"28 Sep 2026, 02:45 PM",dataScope:"Institution",employeeId:"EXT-2022-004",phone:"+91 98765 43210",twoFactorEnabled:!0}],Ed=[{id:"ADM-1024",applicant:"Harpreet Singh",programme:"B.Tech CSE (Sports Analytics)",category:"General",status:"Under Review",submitted:"05 Oct 2026",email:"h.singh2004@gmail.com",phone:"+91 98141 88204",meritRank:42,sportsDiscipline:"Athletics (400m Sprint)",notes:"National School Games Silver Medalist. 10+2 Aggregate: 91.4%",documents:[{id:"DOC-1",name:"Aadhaar Card (UIDAI Verified)",verified:!0,type:"PDF",fileSize:"1.2 MB"},{id:"DOC-2",name:"Class 12th Senior Secondary Marks Card",verified:!0,type:"PDF",fileSize:"2.4 MB"},{id:"DOC-3",name:"Passport Size Photograph & Signature",verified:!0,type:"JPG",fileSize:"480 KB"},{id:"DOC-4",name:"National Sports Merit Certificate",verified:!1,type:"PDF",fileSize:"3.1 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"05 Oct 2026, 09:14 AM",note:"Application fee ₹1,500 settled via HDFC Gateway"},{step:"Documents Uploaded",status:"completed",timestamp:"05 Oct 2026, 09:40 AM",note:"All 4 statutory credentials uploaded"},{step:"Document Verification",status:"in-progress",timestamp:"05 Oct 2026, 02:30 PM",note:"Awaiting sports certificate validation from Dean Sports"},{step:"Counselling & Seat Allotment",status:"pending",timestamp:"Scheduled for 12 Oct 2026"},{step:"Confirmation & Registration",status:"pending",timestamp:"Pending fee deposit"}]},{id:"ADM-1025",applicant:"Simran Kaur",programme:"B.Sc Sports Science & Biomechanics",category:"OBC",status:"Shortlisted",submitted:"05 Oct 2026",email:"simran.kaur.sprt@outlook.com",phone:"+91 97792 10492",meritRank:18,sportsDiscipline:"Shooting (10m Air Rifle)",notes:"Khelo India University Games Gold medalist. State quota eligible.",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.1 MB"},{id:"DOC-2",name:"10+2 Science Board Marks Card",verified:!0,type:"PDF",fileSize:"2.8 MB"},{id:"DOC-3",name:"OBC Non-Creamy Layer Certificate",verified:!0,type:"PDF",fileSize:"1.9 MB"},{id:"DOC-4",name:"Recent Photograph",verified:!0,type:"PNG",fileSize:"650 KB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"05 Oct 2026, 08:30 AM"},{step:"Documents Uploaded",status:"completed",timestamp:"05 Oct 2026, 08:45 AM"},{step:"Document Verification",status:"completed",timestamp:"05 Oct 2026, 04:15 PM",note:"Verified by Prof. S. Dhillon"},{step:"Counselling & Seat Allotment",status:"in-progress",timestamp:"Round 1 counselling call issued"},{step:"Confirmation & Registration",status:"pending",timestamp:"Awaiting candidate acceptance"}]},{id:"ADM-1026",applicant:"Arjun Sharma",programme:"BBA Sports Management",category:"General",status:"Confirmed",submitted:"04 Oct 2026",email:"arjun.sharma.mgt@yahoo.in",phone:"+91 98884 55301",meritRank:5,sportsDiscipline:"Cricket (State U-19)",notes:"Seat confirmed in Merit List 1. Semester tuition fee received in full.",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.0 MB"},{id:"DOC-2",name:"Class 12th Commerce Board Certificate",verified:!0,type:"PDF",fileSize:"3.0 MB"},{id:"DOC-3",name:"Photograph & Specimen Signature",verified:!0,type:"JPG",fileSize:"520 KB"},{id:"DOC-4",name:"Migration Certificate",verified:!0,type:"PDF",fileSize:"1.4 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"04 Oct 2026, 11:20 AM"},{step:"Documents Uploaded",status:"completed",timestamp:"04 Oct 2026, 11:40 AM"},{step:"Document Verification",status:"completed",timestamp:"04 Oct 2026, 03:00 PM"},{step:"Counselling & Seat Allotment",status:"completed",timestamp:"05 Oct 2026, 10:00 AM"},{step:"Confirmation & Registration",status:"completed",timestamp:"05 Oct 2026, 02:40 PM",note:"Fee receipt REC-99214 generated"}]},{id:"ADM-1027",applicant:"Navneet Sandhu",programme:"M.P.Ed (Physical Education)",category:"Sports Quota",status:"Under Review",submitted:"03 Oct 2026",email:"n.sandhu.track@gmail.com",phone:"+91 94170 82910",meritRank:12,sportsDiscipline:"Wrestling (Freestyle 74kg)",notes:"All India Inter-University Bronze Medalist.",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.3 MB"},{id:"DOC-2",name:"B.P.Ed Degree Transcript",verified:!0,type:"PDF",fileSize:"4.2 MB"},{id:"DOC-3",name:"Sports Performance Affidavit",verified:!1,type:"PDF",fileSize:"1.8 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"03 Oct 2026, 02:15 PM"},{step:"Documents Uploaded",status:"completed",timestamp:"03 Oct 2026, 02:35 PM"},{step:"Document Verification",status:"in-progress",timestamp:"Pending trial fitness certificate"},{step:"Counselling & Seat Allotment",status:"pending",timestamp:"Pending"},{step:"Confirmation & Registration",status:"pending",timestamp:"Pending"}]},{id:"ADM-1028",applicant:"Bhavna Rathore",programme:"B.Sc Sports Science & Biomechanics",category:"Defence",status:"Shortlisted",submitted:"03 Oct 2026",email:"bhavna.r.defence@gmail.com",phone:"+91 99150 49182",meritRank:24,sportsDiscipline:"Swimming (200m Breaststroke)",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.0 MB"},{id:"DOC-2",name:"Class 12th Marks Sheet",verified:!0,type:"PDF",fileSize:"2.5 MB"},{id:"DOC-3",name:"Priority V Defence Personnel Ward Certificate",verified:!0,type:"PDF",fileSize:"1.5 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"03 Oct 2026, 10:05 AM"},{step:"Documents Uploaded",status:"completed",timestamp:"03 Oct 2026, 10:25 AM"},{step:"Document Verification",status:"completed",timestamp:"04 Oct 2026, 11:30 AM"},{step:"Counselling & Seat Allotment",status:"in-progress",timestamp:"Allotted Priority 1 seat"},{step:"Confirmation & Registration",status:"pending",timestamp:"Pending"}]},{id:"ADM-1029",applicant:"Taranjeet Singh",programme:"B.Tech CSE (Sports Analytics)",category:"SC/ST",status:"Confirmed",submitted:"02 Oct 2026",email:"t.singh.tech@example.gov",phone:"+91 98155 33019",meritRank:8,sportsDiscipline:"Badminton",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.1 MB"},{id:"DOC-2",name:"Class 12th Non-Medical Transcript",verified:!0,type:"PDF",fileSize:"2.1 MB"},{id:"DOC-3",name:"SC Certificate issued by Tehsildar",verified:!0,type:"PDF",fileSize:"1.4 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"02 Oct 2026, 04:00 PM"},{step:"Documents Uploaded",status:"completed",timestamp:"02 Oct 2026, 04:20 PM"},{step:"Document Verification",status:"completed",timestamp:"03 Oct 2026, 11:00 AM"},{step:"Counselling & Seat Allotment",status:"completed",timestamp:"04 Oct 2026, 09:30 AM"},{step:"Confirmation & Registration",status:"completed",timestamp:"04 Oct 2026, 03:00 PM"}]}],_t=[{id:"ALT-01",title:"RTI deadline approaching",subtitle:"3 applications require immediate statutory PIO response within 48h",category:"Compliance",severity:"critical",timestamp:"10 mins ago"},{id:"ALT-02",title:"Inventory below reorder level",subtitle:"5 items in Sports Physiotherapy Clinic require restocking PO",category:"Inventory",severity:"warning",timestamp:"35 mins ago"},{id:"ALT-03",title:"Grievance case pending",subtitle:"2 student grievance tickets escalated to Proctorial Committee",category:"Grievance",severity:"warning",timestamp:"1 hour ago"},{id:"ALT-04",title:"Payment reconciliation completed",subtitle:"SBI e-Pay portal reconciled ₹1.28 Cr admission receipts for Batch 2026",category:"Finance",severity:"success",timestamp:"2 hours ago"},{id:"ALT-05",title:"System backup completed successfully",subtitle:"Daily snapshot of Oracle ERP Database archived to Disaster Recovery node",category:"System",severity:"info",timestamp:"03:00 AM"}],vs=[{id:"AUD-901",timestamp:"10:42 AM",user:"Demo organisation admin",role:"org-admin",action:"tenancy.organisation.registered",resource:"org: demo-sports-college",status:"Success",ipAddress:"172.16.2.45"},{id:"AUD-902",timestamp:"10:44 AM",user:"System",role:"system",action:"billing.subscription.started",resource:"plan: trial",status:"Success",ipAddress:"127.0.0.1"},{id:"AUD-903",timestamp:"10:51 AM",user:"Demo organisation admin",role:"org-admin",action:"tenancy.organisation.verified",resource:"org: demo-sports-college",status:"Success",ipAddress:"172.16.2.45"},{id:"AUD-904",timestamp:"10:51 AM",user:"System",role:"system",action:"tenancy.package.requested",resource:"kind: registration",status:"Warning",ipAddress:"127.0.0.1"},{id:"AUD-905",timestamp:"11:20 AM",user:"Platform operator",role:"super-admin",action:"tenancy.organisation.approved",resource:"org: demo-sports-college",status:"Success",ipAddress:"10.0.0.12"},{id:"AUD-906",timestamp:"11:20 AM",user:"System",role:"system",action:"tenancy.organisation.activated",resource:"org: demo-sports-college",status:"Success",ipAddress:"127.0.0.1"},{id:"AUD-907",timestamp:"11:34 AM",user:"Demo organisation admin",role:"org-admin",action:"identity.user.created",resource:"role: faculty",status:"Success",ipAddress:"172.16.2.45"},{id:"AUD-908",timestamp:"11:52 AM",user:"Demo organisation admin",role:"org-admin",action:"tenancy.entitlement.changed",resource:"module toggled: academics/lms",status:"Success",ipAddress:"172.16.2.45"},{id:"AUD-909",timestamp:"Yesterday, 05:22 PM",user:"Platform operator",role:"super-admin",action:"tenancy.impersonation.started",resource:"org: demo-sports-college",status:"Warning",ipAddress:"10.0.0.12"}],Ad=[{year:"2023",total:2450,sportsQuota:280,academics:2170},{year:"2024",total:2910,sportsQuota:330,academics:2580},{year:"2025",total:3420,sportsQuota:395,academics:3025},{year:"2026",total:3842,sportsQuota:428,academics:3414}],ws=["#7E22CE","#4338CA","#0369A1","#15803D"],ks=[{stage:"Applications",count:1284,pct:"100%",color:"#9333EA",fill:"#9333EA"},{stage:"Shortlisted",count:824,pct:"64.2%",color:"#7E22CE",fill:"#7E22CE"},{stage:"Counselling",count:612,pct:"47.7%",color:"#16834B",fill:"#16834B"},{stage:"Confirmed",count:486,pct:"37.8%",color:"#F39A19",fill:"#F39A19"}],ln={firstName:"",lastName:"",displayName:"",phone:"",jobTitle:"",bio:"",photo:null,updatedAt:null},Gn="eos-profile-change",_s=n=>`eos.admin.profile.${n}`,jt=new Map;function Cd(n){let t=null;try{t=localStorage.getItem(_s(n))}catch{t=null}const s=jt.get(n);if(s&&s.raw===t)return s.value;let i=ln;try{i=t?{...ln,...JSON.parse(t)}:ln}catch{i=ln}return jt.set(n,{raw:t,value:i}),i}function Pd(n,t){localStorage.setItem(_s(n),JSON.stringify({...t,updatedAt:new Date().toISOString()})),window.dispatchEvent(new Event(Gn))}function Rd(n){return window.addEventListener(Gn,n),window.addEventListener("storage",n),()=>{window.removeEventListener(Gn,n),window.removeEventListener("storage",n)}}function js(n){const t=f.useSyncExternalStore(Rd,()=>Cd(n)),s=f.useCallback(i=>Pd(n,i),[n]);return[t,s]}const Md=["image/jpeg","image/png","image/webp"],Fs=2*1024*1024;async function Dd(n){if(!Md.includes(n.type))throw new Error("Choose a JPG, PNG or WebP image.");if(n.size>Fs)throw new Error(`The image is ${(n.size/1048576).toFixed(1)} MB; the limit is 2 MB.`);const t=URL.createObjectURL(n);try{const s=await new Promise((m,p)=>{const g=new Image;g.onload=()=>m(g),g.onerror=()=>p(new Error("This file could not be read as an image.")),g.src=t}),i=Math.min(s.naturalWidth,s.naturalHeight),a=document.createElement("canvas");a.width=a.height=256;const o=a.getContext("2d");if(!o)throw new Error("This browser cannot process images.");return o.drawImage(s,(s.naturalWidth-i)/2,(s.naturalHeight-i)/2,i,i,0,0,256,256),a.toDataURL("image/jpeg",.88)}finally{URL.revokeObjectURL(t)}}const Cn=n=>n.split(/[\s@.]+/).filter(Boolean).slice(0,2).map(t=>t[0].toUpperCase()).join("")||"AD",Od=[{label:"Dashboard",hint:"dashboard",to:"/dashboard",tag:"NAV"},{label:"Users & Access",hint:"users",to:"/users",tag:"NAV"},{label:"Roles & Permissions",hint:"roles permissions keys",to:"/roles",tag:"NAV"},{label:"Role Dashboards",hint:"dashboards layouts widgets",to:"/dashboards",tag:"NAV"},{label:"Module Registry",hint:"modules entitlement",to:"/modules",tag:"NAV"},{label:"Audit Log",hint:"audit events",to:"/audit-logs",tag:"NAV"},{label:"My Profile",hint:"profile account security",to:"/profile",tag:"NAV"},{label:"Role & Access",hint:"role access permissions api",to:"/access",tag:"NAV"}],Td=({onToggleMobileMenu:n})=>{const t=$e(),s=Fn(),{session:i,signOut:a}=me(),o=i==null?void 0:i.me,[m]=js((o==null?void 0:o.id)??"preview"),p=[m.firstName,m.lastName].filter(Boolean).join(" "),g=m.displayName||p||(o==null?void 0:o.name)||(o==null?void 0:o.email)||"Administrator",u=o?o.is_super_admin?"Super Admin":"Organisation Admin":"Preview",k=g.split(/[\s@.]+/).filter(Boolean).slice(0,2).map(j=>j[0].toUpperCase()).join("")||"AD",[h,l]=f.useState(""),[y,v]=f.useState(!1),[x,F]=f.useState(!1),[E,A]=f.useState(!1),[b,_]=f.useState(!1),C=h.trim().toLowerCase(),L=[...Od,...Xn.map(j=>({label:j.name,hint:j.id,to:fs(j),tag:j.kind==="feature"?"MOD":j.kind==="platform"?"SVC":"INT"}))].filter(j=>!C||j.label.toLowerCase().includes(C)||j.hint.includes(C)).slice(0,8),P=j=>{v(!1),l(""),s(j)},R=f.useRef(null),w=f.useRef(null);f.useEffect(()=>{const j=O=>{R.current&&!R.current.contains(O.target)&&F(!1),w.current&&!w.current.contains(O.target)&&A(!1)};return document.addEventListener("mousedown",j),()=>document.removeEventListener("mousedown",j)},[]),f.useEffect(()=>{const j=O=>{(O.metaKey||O.ctrlKey)&&O.key.toLowerCase()==="k"&&(O.preventDefault(),v(H=>!H)),O.key==="Escape"&&(v(!1),_(!1))};return window.addEventListener("keydown",j),()=>window.removeEventListener("keydown",j)},[]);const M=(()=>{var O;const j=t.pathname;if(j==="/dashboard")return[{label:"Education OS",to:"/dashboard"},{label:"Dashboard"}];if(j==="/users")return[{label:"Administration"},{label:"Users & Access"}];if(j==="/roles")return[{label:"Administration"},{label:"Roles & Permissions"}];if(j==="/admissions")return[{label:"Student Lifecycle",to:"/modules/admissions"},{label:"Admissions Workflow"}];if(j==="/audit-logs")return[{label:"Administration"},{label:"Audit Log"}];if(j==="/profile")return[{label:"Account"},{label:"My Profile"}];if(j==="/access")return[{label:"Account"},{label:"Role & Access"}];if(j==="/dashboards")return[{label:"Administration"},{label:"Role Dashboards"}];if(j==="/modules")return[{label:"Administration"},{label:"Module Registry"}];if(j.startsWith("/modules/")){const H=Je(j.replace("/modules/",""));return[{label:(H&&((O=En(H.suiteId))==null?void 0:O.name))??"Module Registry",to:"/modules"},{label:(H==null?void 0:H.name)??"Unknown module"}]}return[{label:"Education OS",to:"/dashboard"}]})();return e.jsxs(e.Fragment,{children:[e.jsxs("header",{className:"sticky top-0 z-30 h-16 bg-white/80 backdrop-blur-xl border-b border-[#E2E8F0] flex items-center justify-between px-4 sm:px-6",children:[e.jsxs("div",{className:"flex items-center gap-3 sm:gap-4 min-w-0",children:[e.jsx("button",{onClick:n,className:"lg:hidden p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9]","aria-label":"Open navigation menu",children:e.jsx(kr,{className:"w-5 h-5"})}),e.jsx("nav",{className:"flex items-center gap-1.5 text-xs text-[#475569] truncate",children:M.map((j,O)=>e.jsxs($t.Fragment,{children:[O>0&&e.jsx("span",{className:"text-[#64748B]",children:"/"}),j.to&&O<M.length-1?e.jsx(X,{to:j.to,className:"hover:text-[#7E22CE] transition-colors truncate",children:j.label}):e.jsx("span",{className:"font-semibold text-[#12233F] truncate",children:j.label})]},O))})]}),e.jsx("div",{className:"hidden md:flex items-center flex-1 max-w-md mx-6",children:e.jsxs("button",{onClick:()=>v(!0),className:"w-full flex items-center justify-between px-4 py-2 rounded-xl bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] text-xs text-[#475569] shadow-[0_4px_14px_-10px_rgba(60,80,140,0.4)] transition-colors focus:outline-none",children:[e.jsxs("div",{className:"flex items-center gap-2 truncate",children:[e.jsx(ye,{className:"w-3.5 h-3.5 text-[#475569]"}),e.jsx("span",{className:"truncate",children:"Search pages and modules..."})]}),e.jsx("kbd",{className:"hidden sm:inline-flex items-center gap-0.5 text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-full bg-[#F6F8FB] text-[#475569]",children:"Ctrl K"})]})}),e.jsxs("div",{className:"flex items-center gap-2 sm:gap-3",children:[e.jsx("button",{onClick:()=>v(!0),className:"md:hidden p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9]","aria-label":"Search",children:e.jsx(ye,{className:"w-4 h-4"})}),e.jsx("button",{onClick:()=>_(!0),className:"p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9] transition-colors",title:"Institutional Help & Knowledge Base",children:e.jsx(fr,{className:"w-4.5 h-4.5"})}),e.jsxs("div",{className:"relative",ref:R,children:[e.jsxs("button",{onClick:()=>F(!x),className:"relative p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9] transition-colors",title:"Notifications",children:[e.jsx(Qt,{className:"w-4.5 h-4.5"}),e.jsx("span",{className:"absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#DC2626] ring-2 ring-[#F6F8FB] animate-pulse"})]}),x&&e.jsxs("div",{className:"absolute right-0 mt-2 w-80 sm:w-96 rounded-xl bg-[#FFFFFF] border border-[#E2E8F0] shadow-xl py-2 z-50",children:[e.jsxs("div",{className:"flex items-center justify-between px-4 py-2 border-b border-[#E2E8F0]",children:[e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx("span",{className:"font-semibold text-xs text-[#12233F]",children:"Notifications"}),e.jsxs("span",{className:"text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#EBDCFE] text-[#6B21A8]",children:[_t.length," sample"]})]}),e.jsx("button",{onClick:()=>F(!1),className:"text-[11px] text-[#7E22CE] hover:underline font-medium",children:"Close"})]}),e.jsx("div",{className:"max-h-80 overflow-y-auto divide-y divide-[#F1F5F9]",children:_t.map(j=>e.jsxs("div",{className:"p-3 hover:bg-[#F6F8FB] transition-colors flex items-start gap-3",children:[e.jsx("div",{className:"mt-0.5",children:j.severity==="critical"?e.jsx("span",{className:"flex items-center justify-center w-6 h-6 rounded-full bg-[#DC262626] text-[#B91C1C]",children:e.jsx(Ze,{className:"w-3.5 h-3.5"})}):j.severity==="warning"?e.jsx("span",{className:"flex items-center justify-center w-6 h-6 rounded-full bg-[#FEF3E2] text-[#8A4F00]",children:e.jsx(nn,{className:"w-3.5 h-3.5"})}):e.jsx("span",{className:"flex items-center justify-center w-6 h-6 rounded-full bg-[#16834B26] text-[#126B3D]",children:e.jsx(Z,{className:"w-3.5 h-3.5"})})}),e.jsxs("div",{className:"flex-1 min-w-0",children:[e.jsx("p",{className:"text-xs font-semibold text-[#12233F] truncate",children:j.title}),e.jsx("p",{className:"text-[11px] text-[#475569] line-clamp-2 mt-0.5",children:j.subtitle}),e.jsx("span",{className:"text-[10px] text-[#64748B] mt-1 block",children:j.timestamp})]})]},j.id))}),e.jsx("div",{className:"px-4 py-2 border-t border-[#E2E8F0] bg-[#F6F8FB] text-center text-[11px] text-[#475569]",children:"Sample notices: platform/notification is not built yet."})]})]}),e.jsxs("div",{className:"relative pl-1 border-l border-[#E2E8F0]",ref:w,children:[e.jsxs("button",{onClick:()=>A(!E),className:"flex items-center gap-2.5 p-1.5 rounded-lg hover:bg-[#F1F5F9] transition-colors text-left",children:[e.jsxs("div",{className:"hidden sm:block text-right",children:[e.jsx("div",{className:"text-xs font-semibold text-[#12233F] leading-tight",children:g}),e.jsx("div",{className:"text-[11px] text-[#475569] leading-tight",children:u})]}),e.jsx("div",{className:"w-8 h-8 rounded-full bg-[#D03F1B] text-white flex items-center justify-center font-semibold text-xs overflow-hidden",children:m.photo?e.jsx("img",{src:m.photo,alt:"",className:"w-full h-full",style:{objectFit:"cover"}}):k}),e.jsx(en,{className:"w-3.5 h-3.5 text-[#475569]"})]}),E&&e.jsxs("div",{className:"absolute right-0 mt-2 w-56 rounded-xl bg-[#FFFFFF] border border-[#E2E8F0] shadow-xl py-1.5 z-50",children:[e.jsxs("div",{className:"px-3.5 py-2.5 border-b border-[#E2E8F0] bg-[#F6F8FB]",children:[e.jsx("p",{className:"text-xs font-semibold text-[#12233F]",children:g}),e.jsx("p",{className:"text-[11px] text-[#475569] truncate",children:(o==null?void 0:o.email)??"admin@example.org"}),e.jsxs("div",{className:"mt-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#EBDCFE] text-[#6B21A8]",children:[e.jsx(be,{className:"w-3 h-3"}),o!=null&&o.is_super_admin?"Super admin · platform":o?"Organisation admin":"Preview"]})]}),e.jsxs("div",{className:"py-1",children:[e.jsxs("button",{onClick:()=>{A(!1),s("/profile")},className:"w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors",children:[e.jsx(ls,{className:"w-3.5 h-3.5 text-[#475569]"}),e.jsx("span",{children:"Profile"})]}),e.jsxs("button",{onClick:()=>{A(!1),s("/access")},className:"w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors",children:[e.jsx(be,{className:"w-3.5 h-3.5 text-[#475569]"}),e.jsx("span",{children:"Role & Access"})]}),e.jsxs("button",{onClick:()=>{A(!1),s("/profile")},className:"w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors",children:[e.jsx(Pe,{className:"w-3.5 h-3.5 text-[#475569]"}),e.jsx("span",{children:"Security & Audit"})]})]}),e.jsx("div",{className:"border-t border-[#E2E8F0] pt-1",children:e.jsxs("button",{onClick:()=>{A(!1),a(),s("/login",{replace:!0})},className:"w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#B91C1C] hover:bg-[#DC262626]/40 transition-colors font-medium",children:[e.jsx(ss,{className:"w-3.5 h-3.5"}),e.jsx("span",{children:"Logout"})]})})]})]})]})]}),y&&e.jsx("div",{className:"fixed inset-0 z-50 bg-black/30 backdrop-blur-xs flex items-start justify-center pt-20 px-4",onMouseDown:j=>j.target===j.currentTarget&&v(!1),children:e.jsxs("div",{className:"w-full max-w-xl bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden",children:[e.jsxs("div",{className:"flex items-center px-4 py-3 border-b border-[#E2E8F0] gap-3",children:[e.jsx(ye,{className:"w-4 h-4 text-[#475569]"}),e.jsx("input",{type:"text",autoFocus:!0,placeholder:"Search pages and modules...",value:h,onChange:j=>l(j.target.value),onKeyDown:j=>j.key==="Enter"&&L[0]&&P(L[0].to),className:"w-full text-sm text-[#12233F] bg-transparent placeholder-[#64748B] focus:outline-none"}),e.jsx("button",{onClick:()=>v(!1),className:"p-1 rounded text-[#64748B] hover:text-[#12233F]",children:e.jsx(ie,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"p-3 max-h-80 overflow-y-auto space-y-2",children:[e.jsx("div",{className:"text-[11px] font-semibold uppercase text-[#475569] px-2",children:C?"Results":"Quick Navigation"}),L.map(j=>e.jsxs("button",{onClick:()=>P(j.to),className:"w-full flex items-center justify-between p-2 rounded-lg hover:bg-[#F1F5F9] text-left text-xs",children:[e.jsxs("div",{className:"flex items-center gap-2 min-w-0",children:[e.jsx("span",{className:`p-1 rounded font-medium text-[10px] ${j.tag==="NAV"?"bg-[#E7F4EC] text-[#126B3D]":"bg-[#EBDCFE] text-[#6B21A8]"}`,children:j.tag}),e.jsx("span",{className:"font-medium text-[#12233F] truncate",children:j.label})]}),e.jsx("span",{className:"text-[11px] text-[#475569]",children:"Jump →"})]},j.to)),L.length===0&&e.jsxs("p",{className:"px-2 py-3 text-xs text-[#475569]",children:['No page or module matches "',h,'".']})]}),e.jsxs("div",{className:"px-4 py-2 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-[11px] text-[#475569]",children:[e.jsx("span",{children:"Searches pages and modules. Record search needs platform/search (not built)."}),e.jsx("span",{children:"ESC to close"})]})]})}),b&&e.jsx("div",{className:"fixed inset-0 z-50 bg-black/30 backdrop-blur-xs flex items-center justify-center p-4",children:e.jsxs("div",{className:"w-full max-w-lg bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] p-6 space-y-4",children:[e.jsxs("div",{className:"flex items-center justify-between border-b border-[#E2E8F0] pb-3",children:[e.jsxs("div",{className:"flex items-center gap-2.5",children:[e.jsx("div",{className:"p-2 rounded-lg bg-[#EBDCFE] text-[#6B21A8]",children:e.jsx(nr,{className:"w-5 h-5"})}),e.jsxs("div",{children:[e.jsx("h3",{className:"font-semibold text-sm text-[#12233F]",children:"Education OS Help & Documentation"}),e.jsx("p",{className:"text-xs text-[#475569]",children:"Admin console"})]})]}),e.jsx("button",{onClick:()=>_(!1),className:"text-[#475569] hover:text-[#12233F]",children:e.jsx(ie,{className:"w-5 h-5"})})]}),e.jsxs("div",{className:"space-y-3 text-xs text-[#12233F]",children:[e.jsxs("p",{children:["Welcome to the ",e.jsx("strong",{children:"Education OS admin console"}),". Education OS is one multi-tenant platform: each organisation registers, picks its academy type and plan, and sees only its own data."]}),e.jsxs("div",{className:"p-3 rounded-lg bg-[#F1F5F9] border border-[#E2E8F0] space-y-1.5",children:[e.jsx("div",{className:"font-semibold text-[#7E22CE]",children:"Active MVP Screens:"}),e.jsxs("ul",{className:"list-disc list-inside space-y-1 text-[#475569]",children:[e.jsxs("li",{children:[e.jsx("strong",{children:"Dashboard:"})," KPIs, trends, approval queues and upcoming items (sample data)."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Users & Access:"})," Multi-department directory with sliding details drawer."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Roles & Permissions:"})," Roles from the academy profile and the permission keys each module defines."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Admissions:"})," Applicant review screen (sample data; the admissions module is not built yet)."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Role Dashboards, Module Registry, My Profile:"})," layouts, entitlement and your account, from the repo and the API."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Audit Activity:"})," Sample events using the repo's event names; the platform/audit API is not built yet."]})]})]}),e.jsx("p",{className:"text-[11px] text-[#475569]",children:"For assistance, contact your organisation admin, or the platform operator (super admin)."})]}),e.jsx("div",{className:"flex justify-end pt-2",children:e.jsx("button",{onClick:()=>_(!1),className:"px-4 py-2 rounded-lg bg-[#12233F] text-white font-medium text-xs hover:bg-[#12233F] transition-colors",children:"Close Window"})})]})})]})},Bd=()=>{const[n,t]=f.useState(!1),[s,i]=f.useState(!1),[a,o]=f.useState(!0),m=$e(),p=Zn(),{session:g,preview:u}=me(),k=g!=null&&g.trialEndsAt?new Date(g.trialEndsAt).toLocaleDateString("en-IN",{day:"numeric",month:"short",year:"numeric"}):null,h=k?{text:`Trial ends ${k} · ${p.detail}`,link:{to:"/modules",label:"See what your plan includes →"}}:u||!g?{text:"Preview mode: sample data, no API connected.",link:null}:null;return e.jsxs("div",{className:"min-h-screen bg-[#F6F8FB] flex flex-col font-sans",children:[e.jsx(Nd,{collapsed:n,onToggleCollapse:()=>t(!n),mobileOpen:s,onCloseMobile:()=>i(!1)}),e.jsxs("div",{className:`flex-1 flex flex-col transition-all duration-300 ease-in-out ${n?"lg:pl-[72px]":"lg:pl-[260px]"}`,children:[a&&h&&e.jsxs("div",{className:"relative bg-[#08875D] text-white text-[13px] font-medium px-10 py-2 text-center",children:[h.text," ",h.link&&e.jsx(X,{to:h.link.to,className:"underline underline-offset-2 font-semibold hover:text-[#D1FAE5]",children:h.link.label}),e.jsx("button",{onClick:()=>o(!1),"aria-label":"Dismiss announcement",className:"absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center hover:bg-white/15",children:e.jsx(ie,{className:"w-4 h-4"})})]}),e.jsx(Td,{onToggleMobileMenu:()=>i(!s)}),e.jsx("main",{className:"flex-1 p-4 sm:p-6 max-w-7xl w-full mx-auto",children:e.jsx("div",{className:"page-enter",children:e.jsx(Yt,{})},m.pathname)}),e.jsxs("footer",{className:"py-4 px-6 border-t border-[#E2E8F0] text-center text-xs text-[#475569] flex flex-col sm:flex-row items-center justify-between gap-2",children:[e.jsxs("span",{children:["© 2026 ",p.name,". All rights reserved."]}),e.jsxs("div",{className:"flex items-center gap-4 text-[11px]",children:[e.jsx("span",{className:"text-[#64748B] font-medium",children:"Education OS"}),e.jsx("span",{className:"text-[#CBD5E1]",children:"•"}),e.jsx("span",{children:p.detail})]})]})]})]})},Pn={applicant:{description:"Prospective student applying through the admissions portal.",dataScope:"Self",userCount:1842},student:{description:"Enrolled student: timetable, attendance, LMS, exams, fees and campus services.",dataScope:"Self",userCount:3414},athlete:{description:"Student-athlete. Inherits the Student dashboard, plus training, nutrition and tournaments.",dataScope:"Self",userCount:428},faculty:{description:"Teaches courses, marks attendance, grades LMS work and performs exam duties.",dataScope:"Assigned Records",userCount:312},coach:{description:"Plans training, reviews video, manages squads and books sports facilities. Inherits the Faculty dashboard.",dataScope:"Assigned Records",userCount:42},"medical-staff":{description:"Tracks injuries, physio appointments and fitness clearances.",dataScope:"Assigned Records",userCount:9},nutritionist:{description:"Builds and reviews athlete diet plans and body-composition trends.",dataScope:"Assigned Records",userCount:4},"examination-staff":{description:"Schedules exams, issues hall tickets, processes and publishes results.",dataScope:"Institution",userCount:6},"department-admin":{description:"Runs a department: approvals, faculty load, attendance and results.",dataScope:"Department",userCount:18},"finance-staff":{description:"Fee collection, payment reconciliation, budgets and purchase orders.",dataScope:"Institution",userCount:8},"hr-staff":{description:"Leave, payroll runs, joinings and exits, and e-office file movement.",dataScope:"Institution",userCount:7},"facility-staff":{description:"Bookings, maintenance tickets, stock levels and asset audits.",dataScope:"Department",userCount:21},governance:{description:"Grievances, RTI deadlines, IQAC and regulatory returns.",dataScope:"Institution",userCount:11},"support-staff":{description:"Triages tickets, watches SLA breaches, incidents and AMC renewals.",dataScope:"Assigned Records",userCount:15},management:{description:"Institution leadership: admissions, finance, results, compliance and productions at a glance.",dataScope:"Institution",userCount:5},"org-admin":{description:"Created at registration. Users, roles, settings and subscription of one organisation.",dataScope:"Institution",userCount:1},"super-admin":{description:"Platform operator outside every organisation: approves organisations and academic packages, plans, subscriptions, overrides and audited impersonation.",dataScope:"Institution",userCount:1}},Ld=new Set(Vt.map(n=>n.id));function Ns(n){return Ht(n.roles).map(t=>{var s,i,a;return{id:t.id,title:t.title,description:((s=Pn[t.id])==null?void 0:s.description)??"",dataScope:((i=Pn[t.id])==null?void 0:i.dataScope)??"Self",userCount:((a=Pn[t.id])==null?void 0:a.userCount)??0,system:Ld.has(t.id),permissions:Qn([t.id],t.id==="super-admin")}})}const Ss=n=>Object.fromEntries(n.flatMap(t=>gn[t.id]?[[t.id,gn[t.id]]]:[])),Es=Ns(hn);function et(){const t=Se().profile??hn;return f.useMemo(()=>{const s=Ns(t);return{ROLES:s,ROLE_LAYOUTS:Ss(s),ROLES_SOURCE:`platform/identity/config/profiles/${t.profile}.yaml`,ROLES_PROFILE_TITLE:t.title}},[t])}const Id=new Map([...Object.values(Re).flatMap(n=>Ht(n.roles).map(t=>[t.id,t.title])),...Vt.map(n=>[n.id,n.title])]),yn=n=>Es.find(t=>t.id===n),re=n=>{var t;return((t=yn(n))==null?void 0:t.title)??Id.get(n)??n},As=Ss(Es),qe=n=>oa(n,gn),Ue=n=>n.split(".")[0],qd=n=>Object.keys(As).filter(t=>qe(t).some(s=>Ue(s)===n)),$d=n=>[...new Set(Object.keys(As).flatMap(qe))].filter(t=>Ue(t)===n),Cs=()=>{var n;return typeof window<"u"&&!!((n=window.matchMedia)!=null&&n.call(window,"(prefers-reduced-motion: reduce)").matches)};function rn(n,t=.45,s=120){const[i,a]=f.useState(()=>typeof IntersectionObserver>"u"||Cs());return f.useEffect(()=>{const o=n.current;if(i||!o)return;let m=0;const p=new IntersectionObserver(g=>{g.some(u=>u.isIntersecting)&&(p.disconnect(),m=window.setTimeout(()=>a(!0),s))},{threshold:t});return p.observe(o),()=>{p.disconnect(),window.clearTimeout(m)}},[n,i,t,s]),i}const Wn=n=>1-Math.pow(1-n,3);function Ps(n,t){const s=Cs(),[i,a]=f.useState(s?t:0);return f.useEffect(()=>{if(!n||s)return;let o=0;const m=performance.now(),p=g=>{const u=Math.min(t,g-m);a(u),u<t&&(o=requestAnimationFrame(p))};return o=requestAnimationFrame(p),()=>cancelAnimationFrame(o)},[n,t,s]),i}const _e=({end:n,decimals:t=0,prefix:s="",suffix:i="",duration:a=1e3,active:o=!0,delay:m=0})=>{const p=Ps(o,a+m),g=Math.max(0,Math.min(1,(p-m)/a)),u=g>=1?n:n*Wn(g);return e.jsxs(e.Fragment,{children:[s,u.toLocaleString("en-IN",{minimumFractionDigits:t,maximumFractionDigits:t}),i]})},Vd={brand:"linear-gradient(90deg,rgba(112,14,92,0.94) 0%,rgba(84,24,140,0.86) 30%,rgba(55,48,163,0.45) 52%,rgba(49,46,129,0.08) 70%,transparent 82%)",violet:"linear-gradient(90deg,rgba(109,40,217,0.95) 0%,rgba(91,33,182,0.86) 30%,rgba(67,56,202,0.45) 52%,rgba(67,56,202,0.08) 70%,transparent 82%)"},nt=({src:n=B("/campus.jpg"),position:t="62% 72%",tone:s="brand",fit:i="full"})=>i==="right"?e.jsx("div",{className:"absolute inset-y-0 right-0 w-[64%] bg-cover bg-no-repeat [mask-image:linear-gradient(to_right,transparent_0%,black_35%)]",style:{backgroundImage:`url('${n}')`,backgroundPosition:t}}):e.jsxs(e.Fragment,{children:[e.jsx("div",{className:"absolute inset-0 bg-cover bg-no-repeat",style:{backgroundImage:`url('${n}')`,backgroundPosition:t}}),e.jsx("div",{className:"absolute inset-0",style:{backgroundImage:Vd[s]}}),e.jsx("div",{className:"absolute inset-x-0 bottom-0 h-1/2 bg-[linear-gradient(to_top,rgba(17,12,48,0.35),transparent)]"})]}),Hd=({values:n,colors:t,delay:s=0})=>{const i=Math.max(...n),a=Math.min(...n);return e.jsx("div",{className:"flex items-end gap-[3px] w-24 h-[30px]","aria-hidden":!0,children:n.map((o,m)=>e.jsx("span",{className:"flex-1 rounded-t-[2px] origin-bottom eos-kpi-col",style:{height:`${30+(o-a)/(i-a||1)*70}%`,backgroundColor:t[m%t.length],animationDelay:`${s+m*90}ms`}},m))})},Ud=({slices:n,delay:t=0})=>{const i=2*Math.PI*8,a=n.reduce((m,p)=>m+p.value,0)||1;let o=0;return e.jsxs("svg",{viewBox:"0 0 32 32",className:"w-8 h-8 -rotate-90","aria-hidden":!0,children:[n.map((m,p)=>{const g=m.value/a*i,u=-o;return o+=g,e.jsx("circle",{cx:"16",cy:"16",r:8,fill:"none",stroke:m.color,strokeWidth:2*8,strokeDashoffset:u,className:"eos-kpi-seg",style:{"--seg":`${g}`,"--seg-c":`${i}`,animationDelay:`${t+p*140}ms`}},p)}),e.jsx("circle",{cx:"16",cy:"16",r:"15.5",fill:"none",stroke:"#FFFFFF",strokeOpacity:"0.9",strokeWidth:"1"})]})},Gd=({stacks:n,colors:t,delay:s=0})=>{const i=Math.max(...n.map(a=>a.reduce((o,m)=>o+m,0)))||1;return e.jsx("div",{className:"flex items-end gap-[3px] w-24 h-[30px]","aria-hidden":!0,children:n.map((a,o)=>{const m=a.reduce((p,g)=>p+g,0);return e.jsx("span",{className:"flex-1 flex flex-col-reverse overflow-hidden rounded-t-[2px] origin-bottom eos-kpi-col",style:{height:`${m/i*100}%`,animationDelay:`${s+o*90}ms`},children:a.map((p,g)=>e.jsx("span",{style:{height:`${p/m*100}%`,backgroundColor:t[g%t.length]}},g))},o)})})},Wd=({slices:n,of:t,delay:s=0})=>{const a=2*Math.PI*12,o=t??(n.reduce((p,g)=>p+g.value,0)||1);let m=0;return e.jsxs("svg",{viewBox:"0 0 32 32",className:"w-8 h-8 -rotate-90","aria-hidden":!0,children:[e.jsx("circle",{cx:"16",cy:"16",r:12,fill:"none",stroke:"#E3E7EE",strokeWidth:"5"}),n.map((p,g)=>{const u=p.value/o*a,k=-m;return m+=u,e.jsx("circle",{cx:"16",cy:"16",r:12,fill:"none",stroke:p.color,strokeWidth:"5",strokeDashoffset:k,className:"eos-kpi-seg",style:{"--seg":`${Math.max(0,u-.6)}`,"--seg-c":`${a}`,animationDelay:`${s+g*140}ms`}},g)})]})},Yd=({bars:n,delay:t=0})=>{const s=Math.max(...n.map(i=>i.value))||1;return e.jsx("div",{className:"flex flex-col justify-end gap-[2.5px] w-24 h-[30px]","aria-hidden":!0,children:n.map((i,a)=>e.jsx("span",{className:"block h-1 rounded-full origin-left eos-kpi-bar",style:{width:`${i.value/s*100}%`,backgroundColor:i.color,animationDelay:`${t+a*120}ms`}},a))})},zd=({value:n,zones:t,delay:s=0})=>{const i="M6 26 A18 18 0 0 1 42 26";let a=0;return e.jsxs("svg",{viewBox:"0 0 48 30",className:"w-12 h-[30px] overflow-visible","aria-hidden":!0,children:[t.map((o,m)=>{const p=o.to-a-(m<t.length-1?.025:0),g=e.jsx("path",{d:i,fill:"none",stroke:o.color,strokeWidth:"5",pathLength:1,strokeDasharray:`${p} 1`,strokeDashoffset:-a},m);return a=o.to,g}),e.jsx("g",{className:"eos-kpi-needle",style:{"--needle":`${-90+n*180}deg`,animationDelay:`${s}ms`},children:e.jsx("line",{x1:"24",y1:"26",x2:"24",y2:"12",stroke:"#12233F",strokeWidth:"1.8",strokeLinecap:"round"})}),e.jsx("circle",{cx:"24",cy:"26",r:"2.6",fill:"#12233F"})]})},Ft=[{accent:"#315EA8",chipBg:"#FFFFFF",chipFg:"#315EA8",tint:"#F3F7FD",border:"#DCE5F3"},{accent:"#159A72",chipBg:"#FFFFFF",chipFg:"#127F5E",tint:"#F1FAF6",border:"#D3EEE4"},{accent:"#E45B67",chipBg:"#FFFFFF",chipFg:"#C9414E",tint:"#FEF5F6",border:"#F7DCDF"},{accent:"#22A06B",chipBg:"#FFFFFF",chipFg:"#1B8458",tint:"#F2FAF6",border:"#D4EEE2"},{accent:"#6256C9",chipBg:"#FFFFFF",chipFg:"#5247B5",tint:"#F6F5FD",border:"#E1DEF6"},{accent:"#E89A35",chipBg:"#FFFFFF",chipFg:"#B8721A",tint:"#FEF9F2",border:"#F6E6CD"}],Kd={up:"text-[#126B3D]",alert:"text-[#B91C1C]",muted:"text-[#475569]"},Qd={navy:"bg-[var(--accent-tint)] text-[var(--accent)] ring-[var(--accent-ring)]",green:"bg-[#EEF7F1] text-[#126B3D] ring-[#CDE8D8]",orange:"bg-[#FFF8EC] text-[#A35F00] ring-[#FBE3BD]",coral:"bg-[#FEF2F2] text-[#B91C1C] ring-[#FECACA]"},Jd=(n,t)=>n===0?"navy":t==="alert"?"orange":t==="up"?"green":"navy",Xd=({label:n,value:t,icon:s,delta:i,deltaTone:a="up",note:o,index:m=0,accent:p,to:g,palette:u,viz:k})=>{const h=e.jsxs(e.Fragment,{children:[e.jsxs("div",{className:"flex items-start justify-between gap-2",children:[e.jsx("span",{className:"text-[13px] font-medium leading-snug text-[#5B6B82]",children:n}),u?e.jsx("span",{className:"w-9 h-9 rounded-[10px] flex items-center justify-center flex-shrink-0 shadow-[0_1px_3px_rgba(16,24,40,0.08)] transition-colors duration-200 bg-[var(--chip-bg)] text-[var(--chip-fg)] group-hover:bg-[var(--chip-fg)] group-hover:text-white",children:e.jsx(s,{className:"w-4 h-4"})}):e.jsx("span",{className:`w-8 h-8 rounded-lg ring-1 flex items-center justify-center flex-shrink-0 ${Qd[p??Jd(m,a)]}`,children:e.jsx(s,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"mt-auto pt-3 flex items-end justify-between gap-4",children:[e.jsxs("div",{className:"min-w-0",children:[e.jsx("div",{className:"text-[30px] leading-none font-extrabold tracking-[-0.02em] text-[#12233F] tabular-nums break-words",children:t}),(i||o)&&e.jsxs("div",{className:"mt-2 text-[12px] leading-snug",children:[i&&e.jsxs("span",{className:`inline-flex items-center gap-1 font-semibold ${Kd[a]}`,children:[a==="alert"&&e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-[#DC2626]"}),i]}),i&&o&&e.jsx("span",{className:"text-[#CBD5E1]",children:" · "}),o&&e.jsx("span",{className:"text-[#64748B]",children:o})]})]}),k&&e.jsx("div",{className:"flex-shrink-0 w-24 h-[30px] flex items-end justify-end pb-1",children:k})]})]}),l="group relative flex flex-col h-full min-h-[150px] overflow-hidden rounded-[14px] border border-[#E4E8EF] bg-white px-6 pt-5 pb-5 min-w-0 shadow-[0_1px_2px_rgba(16,24,40,0.03)] transition-[box-shadow,border-color] duration-200 ease-out hover:border-[var(--card-ring)] hover:shadow-[0_10px_24px_-14px_var(--card-shadow)]",y={animationDelay:`${m*60}ms`,"--card-ring":u?`${u.accent}55`:"var(--accent-ring)","--card-shadow":u?`${u.accent}55`:"rgba(15,23,42,0.25)",...u?{"--chip-bg":u.chipBg,"--chip-fg":u.chipFg,backgroundColor:u.tint,borderColor:u.border}:{}};return g?e.jsx(X,{to:g,className:`${l} focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]`,style:y,children:h}):e.jsx("div",{className:l,style:y,children:h})},xe=({stats:n,label:t="Key metrics",colorful:s=!1})=>e.jsx("section",{"aria-label":t,className:`grid gap-5 grid-cols-1 min-[420px]:grid-cols-2 ${n.length>4?"md:grid-cols-3 2xl:grid-cols-6":"lg:grid-cols-4"}`,children:n.map((i,a)=>e.jsx(Xd,{index:a,palette:s?Ft[a%Ft.length]:void 0,...i},i.label))}),ve=({title:n,subtitle:t,eyebrow:s,actions:i,art:a})=>a?e.jsxs("header",{className:"eos-hero relative overflow-visible rounded-xl text-white min-h-[200px] md:min-h-[240px] flex items-end",children:[e.jsx("div",{"aria-hidden":!0,className:"pointer-events-none absolute inset-0 overflow-hidden rounded-xl",children:a}),e.jsxs("div",{className:"relative z-10 px-6 py-7 sm:px-9 max-w-[560px]",children:[s&&e.jsx("div",{className:"eos-hero-sub text-[12px] font-medium mb-1.5",children:s}),e.jsx("h1",{className:"text-[32px] leading-tight font-bold tracking-[-0.02em] text-white",children:n}),t&&e.jsx("div",{className:"eos-hero-sub text-[14px] mt-1.5",children:t}),i&&e.jsx("div",{className:"mt-5 flex flex-wrap items-center gap-2.5",children:i})]})]}):e.jsxs("header",{className:"eos-hero relative rounded-xl px-6 py-7 sm:px-8 flex flex-col md:flex-row md:items-end md:justify-between gap-5 text-white",children:[e.jsxs("div",{className:"relative z-10 min-w-0",children:[s&&e.jsx("div",{className:"eos-hero-sub text-[12px] font-medium mb-1.5",children:s}),e.jsx("h1",{className:"text-[30px] leading-tight font-bold tracking-[-0.02em] text-white",children:n}),t&&e.jsx("div",{className:"eos-hero-sub text-sm mt-1.5",children:t})]}),i&&e.jsx("div",{className:"relative z-10 flex flex-wrap items-center gap-2",children:i})]}),je="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-[#F65B66] text-white text-[13px] font-semibold hover:bg-[#E9505C] transition-colors eos-btn-primary",ae="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-white border border-[#E2E8F0] text-xs font-semibold text-[#12233F] hover:border-[#CBD5E1] hover:bg-[#F6F8FB] transition-colors eos-btn-secondary",Nt="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-white border border-[#FECACA] text-xs font-semibold text-[#B91C1C] hover:bg-[#FEF2F2] transition-colors",z="bg-white border border-[#E2E8F0] rounded-xl",K=({title:n,subtitle:t,action:s})=>e.jsxs("div",{className:"flex items-start justify-between gap-4 px-5 pt-4 pb-3",children:[e.jsxs("div",{className:"min-w-0",children:[e.jsx("h2",{className:"text-[15px] font-semibold text-[#12233F]",children:n}),t&&e.jsx("p",{className:"text-xs text-[#64748B] mt-0.5",children:t})]}),s]}),Rs=n=>null,Ms=n=>null,Ds=n=>null,bn=n=>null,tt=n=>null,st=n=>null;function Zd({width:n="100%",height:t="100%",children:s}){const i=f.useRef(null),[a,o]=f.useState(null);f.useLayoutEffect(()=>{const p=i.current;if(!p)return;const g=()=>o({w:p.clientWidth,h:p.clientHeight});g();const u=new ResizeObserver(g);return u.observe(p),()=>u.disconnect()},[]);const m=rn(i);return e.jsx("div",{ref:i,className:"recharts-responsive-container",style:{width:n,height:t,minWidth:0},children:e.jsx("div",{style:{width:0,height:0,overflow:"visible"},children:a&&a.w>0&&a.h>0&&f.cloneElement(s,{width:a.w,height:a.h,active:m})})})}function Os(n){const t=[];return f.Children.forEach(n,s=>{f.isValidElement(s)&&(s.type===f.Fragment?t.push(...Os(s.props.children)):t.push(s))}),t}function Xe(n,t){var s;return(s=n.find(i=>i.type===t))==null?void 0:s.props}function xn(n,t){return n.filter(s=>s.type===t).map(s=>s.props)}const vn=n=>Number(n.toPrecision(12));function ec(n,t){if(n<=0)return 0;const s=Math.floor(Math.log10(n))+1,i=10**s,a=n/i,o=s!==1?.05:.1;return vn((Math.ceil(vn(a/o))+t)*o*i)}function Ts(n,t=5,s=0){if(n<=0)return[0,1,2,3,4].slice(0,t);const i=ec(n/(t-1),s);let a=Math.ceil(vn(n/i));const o=a+1;return o>t?Ts(n,t,s+1):(o<t&&(a+=t-o),Array.from({length:a+1},(m,p)=>vn(p*i)))}function St(n){let t=document.getElementById("recharts_measurement_span");t||(t=document.createElement("span"),t.id="recharts_measurement_span",t.setAttribute("aria-hidden","true"),document.body.appendChild(t)),Object.assign(t.style,{position:"absolute",top:"-20000px",left:0,padding:0,margin:0,border:"none",whiteSpace:"pre"}),t.textContent=n;const s=t.getBoundingClientRect();return{width:s.width,height:s.height}}function Et(n,t,s,i){const a=n.length>=2&&Math.sign(n[1]-n[0])||1,[o,m]=a===1?[s,i]:[i,s];let p=m;const g=[];for(let u=n.length-1;u>=0;u--){const k=t[u];let h=n[u];if(u===n.length-1){const y=a*(h+a*k/2-p);y>0&&(h-=y*a)}!(a*h<a*o||a*h>a*p)&&a*(h-a*k/2-o)>=0&&a*(h+a*k/2-p)<=0&&(p=h-a*(k/2+5),g.push({i:u,at:h}))}return g.reverse()}const nc=()=>{var n;return typeof window<"u"&&!!((n=window.matchMedia)!=null&&n.call(window,"(prefers-reduced-motion: reduce)").matches)},ne=n=>Math.round(n*1e3)/1e3,dn=n=>Math.round(n*1e4)/1e4;function At(n){const t=n.length;if(t===0)return"";if(t===1)return`M${ne(n[0].x)},${ne(n[0].y)}`;if(t===2)return`M${ne(n[0].x)},${ne(n[0].y)}L${ne(n[1].x)},${ne(n[1].y)}`;const s=p=>p<0?-1:1,i=(p,g,u,k,h,l)=>{const y=u-p,v=h-u,x=(k-g)/(y||(v<0?-0:0)),F=(l-k)/(v||(y<0?-0:0)),E=(x*v+F*y)/(y+v);return(s(x)+s(F))*Math.min(Math.abs(x),Math.abs(F),.5*Math.abs(E))||0},a=(p,g,u,k,h)=>{const l=u-p;return l?(3*(k-g)/l-h)/2:h},o=new Array(t);for(let p=1;p<t-1;p++)o[p]=i(n[p-1].x,n[p-1].y,n[p].x,n[p].y,n[p+1].x,n[p+1].y);o[0]=a(n[0].x,n[0].y,n[1].x,n[1].y,o[1]),o[t-1]=a(n[t-2].x,n[t-2].y,n[t-1].x,n[t-1].y,o[t-2]);let m=`M${ne(n[0].x)},${ne(n[0].y)}`;for(let p=0;p<t-1;p++){const g=n[p],u=n[p+1],k=(u.x-g.x)/3;m+=`C${ne(g.x+k)},${ne(g.y+k*o[p])},${ne(u.x-k)},${ne(u.y-k*o[p+1])},${ne(u.x)},${ne(u.y)}`}return m}function tc(n,t,s,i){const a=3*n,o=3*(s-n)-a,m=1-a-o,p=3*t,g=3*(i-t)-p,u=1-p-g,k=y=>((m*y+o)*y+a)*y,h=y=>((u*y+g)*y+p)*y,l=y=>(3*m*y+2*o)*y+a;return y=>{let v=y;for(let x=0;x<8;x++){const F=k(v)-y,E=l(v);if(Math.abs(F)<1e-6||Math.abs(E)<1e-6)break;v-=F/E}return h(Math.min(1,Math.max(0,v)))}}const sc=tc(.25,.1,.25,1);function ac(n,t=!0){var o;const s=typeof window<"u"&&((o=window.matchMedia)==null?void 0:o.call(window,"(prefers-reduced-motion: reduce)").matches),[i,a]=f.useState(s?1:0);return f.useEffect(()=>{if(s||!t)return;let m=0;const p=performance.now(),g=u=>{const k=Math.min(1,(u-p)/n);a(sc(k)),k<1&&(m=requestAnimationFrame(g))};return m=requestAnimationFrame(g),()=>cancelAnimationFrame(m)},[n,s,t]),i}function ic(n,t,s,i,a){if(i<=0||s<=0)return"";const o=Math.min(a,s/2,i);return[n,t,s,i]=[dn(n),dn(t),dn(s),dn(i)],`M${n},${t+o}A${o},${o},0,0,1,${n+o},${t}L${n+s-o},${t}A${o},${o},0,0,1,${n+s},${t+o}L${n+s},${t+i}L${n},${t+i}Z`}function Bs(n,t){const{data:s,width:i=0,height:a=0}=t,o={top:5,right:5,left:5,bottom:5,...t.margin},m=Os(t.children),p=Xe(m,Rs)??{},g=Xe(m,Ms)??{},u=(n==="bar"?xn(m,tt):xn(m,st)).map(_=>_.dataKey),k=g.width??60,h=p.height??30,l={left:o.left+k,top:o.top,width:Math.max(0,i-o.left-o.right-k),height:Math.max(0,a-o.top-o.bottom-h)},y=Math.max(0,...s.flatMap(_=>u.map(C=>Number(_[C])||0))),v=Ts(y),x=v[v.length-1]||1,F=_=>l.top+l.height-_/x*l.height,E=s.length,A=E?l.width/E:0;return{items:m,x:p,y:g,frame:l,ticks:v,yOf:F,xOf:_=>n==="bar"?l.left+A*_+A/2:l.left+(E>1?l.width*_/(E-1):l.width/2),band:A,n:E}}function Ls({chart:n,draw:t=1}){const{frame:s,ticks:i,yOf:a,items:o}=n,m=Xe(o,Ds);return m?e.jsx("g",{className:"recharts-cartesian-grid",children:e.jsx("g",{className:"recharts-cartesian-grid-horizontal",children:i.map(p=>e.jsx("line",{stroke:m.stroke??"#ccc",fill:"none",x1:s.left,y1:a(p),x2:s.left+s.width*t,y2:a(p)},p))})}):null}function Is({chart:n}){const{x:t,frame:s}=n;if(t.axisLine===!1)return null;const i=(typeof t.axisLine=="object"?t.axisLine.stroke:void 0)??t.stroke??"#666",a=s.top+s.height;return e.jsx("g",{className:"recharts-layer recharts-cartesian-axis recharts-xAxis xAxis",children:e.jsx("line",{className:"recharts-cartesian-axis-line",stroke:i,fill:"none",x1:s.left,y1:a,x2:s.left+s.width,y2:a})})}function qs({chart:n,labels:t,width:s,height:i}){const{x:a,y:o,frame:m,ticks:p,yOf:g,xOf:u,n:k}=n,h=o.tickFormatter??(F=>String(F)),l=p.map(F=>h(F)),y=Et(Array.from({length:k},(F,E)=>u(E)),t.map(F=>St(F).width),0,s),v=Et(p.map(F=>g(F)),l.map(F=>St(F).height),0,i),x=m.top+m.height+8;return e.jsxs(e.Fragment,{children:[e.jsx("g",{className:"recharts-layer recharts-cartesian-axis-tick-labels recharts-xAxis-tick-labels",children:y.map(({i:F,at:E})=>e.jsx("text",{className:"recharts-text recharts-cartesian-axis-tick-value",x:E,y:x,textAnchor:"middle",fontSize:a.fontSize,fill:a.stroke??"#666",stroke:"none",children:e.jsx("tspan",{x:E,dy:"0.71em",children:t[F]})},F))}),e.jsx("g",{className:"recharts-layer recharts-cartesian-axis-tick-labels recharts-yAxis-tick-labels",children:v.map(({i:F,at:E})=>e.jsx("text",{className:"recharts-text recharts-cartesian-axis-tick-value",x:m.left-8,y:E,textAnchor:"end",fontSize:o.fontSize,fill:o.stroke??"#666",stroke:"none",children:e.jsx("tspan",{x:m.left-8,dy:"0.355em",children:l[F]})},F))})]})}function $s({tip:n,frame:t,at:s,label:i,entries:a}){const o=f.useRef(null),[m,p]=f.useState(null);f.useLayoutEffect(()=>{if(!s||!o.current)return;const{width:u,height:k}=o.current.getBoundingClientRect(),h=(l,y,v,x)=>{const F=l+10;return F+y>v+x?Math.max(l-10-y,v):Math.max(F,v)};p({x:h(s.x,u,t.left,t.width),y:h(s.y,k,t.top,t.height)})},[s,t.left,t.top,t.width,t.height,i]);const g=n.formatter??((u,k)=>[String(u),String(k)]);return e.jsx("div",{className:"recharts-tooltip-wrapper",style:{visibility:s&&m?"visible":"hidden",pointerEvents:"none",position:"absolute",top:0,left:0,outline:"none",transform:m?`translate(${m.x}px, ${m.y}px)`:void 0,transition:s&&m&&!nc()?"transform 400ms ease":void 0},children:e.jsxs("div",{ref:o,className:"recharts-default-tooltip",role:"status","aria-live":"assertive",style:{margin:0,padding:10,backgroundColor:"#fff",border:"1px solid #ccc",whiteSpace:"nowrap",...n.contentStyle},children:[e.jsx("p",{className:"recharts-tooltip-label",style:{margin:0,...n.labelStyle},children:n.labelFormatter?n.labelFormatter(i):String(i)}),e.jsx("ul",{className:"recharts-tooltip-item-list",style:{padding:0,margin:0},children:a.map(u=>{const[k,h]=g(u.value,u.name);return e.jsxs("li",{className:"recharts-tooltip-item",style:{display:"block",paddingTop:4,paddingBottom:4,...n.itemStyle},children:[e.jsx("span",{className:"recharts-tooltip-item-name",children:h}),e.jsx("span",{className:"recharts-tooltip-item-separator",children:" : "}),e.jsx("span",{className:"recharts-tooltip-item-value",children:k}),e.jsx("span",{className:"recharts-tooltip-item-unit"})]},u.name)})})]})})}function Vs(n,t){const[s,i]=f.useState(null);return{hover:s,onMove:o=>{const m=o.currentTarget.getBoundingClientRect(),p=o.clientX-m.left,g=o.clientY-m.top,{frame:u,n:k,band:h}=n;if(!k||p<u.left||p>u.left+u.width||g<u.top||g>u.top+u.height){i(null);return}const l=t==="bar"?Math.min(k-1,Math.floor((p-u.left)/h)):Math.round((p-u.left)/(u.width||1)*(k-1));i({i:Math.max(0,l),y:g})},onLeave:()=>i(null)}}function Hs({width:n,height:t,children:s,svg:i}){return e.jsxs("div",{className:"recharts-wrapper",style:{position:"relative",cursor:"default",width:n,height:t},children:[s,i]})}function rc(n){var J,U;const t=Bs("bar",n),{items:s,frame:i,yOf:a,band:o,n:m,x:p}=t,g=xn(s,tt),u=Xe(s,bn),k=500,h=1e3,l=140,y=110,v=Ps(n.active??!0,k+h+l*Math.max(0,t.n-1)+y*2),x=Wn(Math.min(1,v/k)),F=(V,te=0)=>Wn(Math.max(0,Math.min(1,(v-k*.6-V*l-te*y)/h))),{hover:E,onMove:A,onLeave:b}=Vs(t,"bar"),{data:_,width:C=0,height:L=0,barGap:P=4}=n,R=_.map(V=>String(V[p.dataKey??""]??"")),w=typeof n.barCategoryGap=="string"?parseFloat(n.barCategoryGap)/100:(n.barCategoryGap??.1*o)/(o||1),T=o*w;let M=P;o-2*T-(g.length-1)*M<=0&&(M=0);let j=(o-2*T-(g.length-1)*M)/Math.max(1,g.length);j>1&&(j=Math.round(j));const O=Math.min(j,((J=g[0])==null?void 0:J.maxBarSize)??1/0),H=i.top+i.height,oe=e.jsxs("svg",{className:"recharts-surface",width:C,height:L,viewBox:`0 0 ${C} ${L}`,style:{width:"100%",height:"100%",display:"block"},onMouseMove:A,onMouseLeave:b,children:[e.jsx(Ls,{chart:t,draw:x}),u&&E&&e.jsx("rect",{className:"recharts-tooltip-cursor",x:i.left+o*E.i,y:i.top,width:o,height:i.height,fill:((U=u.cursor)==null?void 0:U.fill)??"#ccc",stroke:"none",pointerEvents:"none"}),g.map((V,te)=>e.jsx("g",{className:"recharts-layer recharts-bar",children:_.map((G,ee)=>{var de;const pe=Number(G[V.dataKey])||0,we=(H-a(pe))*F(ee,te),ue=i.left+o*ee+T+g.length*(j-O)/2+(O+M)*te,le=E&&E.i!==ee;return e.jsx("path",{className:"recharts-rectangle",fill:V.fill,fillOpacity:le?.55:1,style:{transition:"fill-opacity 160ms ease"},d:ic(ue,H-we,O,we,((de=V.radius)==null?void 0:de[0])??0)},ee)})},V.dataKey)),e.jsx(Is,{chart:t}),e.jsx(qs,{chart:t,labels:R,width:C,height:L})]});return e.jsx(Hs,{width:C,height:L,svg:oe,children:u&&m>0&&e.jsx($s,{tip:u,frame:i,at:E?{x:t.xOf(E.i),y:E.y}:null,label:E?R[E.i]:"",entries:E?g.map(V=>({name:V.name??V.dataKey,value:_[E.i][V.dataKey]})):[]})})}let oc=0;function lc(n){var L,P;const t=Bs("area",n),{items:s,frame:i,yOf:a,xOf:o,n:m,x:p}=t,g=xn(s,st),u=Xe(s,bn),k=s.filter(R=>R.type==="defs"),h=ac(((L=g[0])==null?void 0:L.animationDuration)??1500,n.active??!0),{hover:l,onMove:y,onLeave:v}=Vs(t,"area"),[x]=f.useState(()=>`eos-area-clip-${++oc}`),{data:F,width:E=0,height:A=0}=n,b=F.map(R=>String(R[p.dataKey??""]??"")),_=i.top+i.height,C=e.jsxs("svg",{className:"recharts-surface",width:E,height:A,viewBox:`0 0 ${E} ${A}`,style:{width:"100%",height:"100%",display:"block"},onMouseMove:y,onMouseLeave:v,children:[k,e.jsx("defs",{children:e.jsx("clipPath",{id:x,children:e.jsx("rect",{x:i.left,y:0,width:(i.width+1)*h,height:A})})}),e.jsx(Ls,{chart:t}),g.map(R=>{const w=F.map((O,H)=>({x:o(H),y:a(Number(O[R.dataKey])||0)})),T=At(w),M=At(w.map(O=>({x:O.x,y:_})).reverse()),j=w.length?`${T}L${M.slice(1)}Z`:"";return e.jsxs("g",{className:"recharts-layer recharts-area",clipPath:h<1?`url(#${x})`:void 0,children:[e.jsx("path",{className:"recharts-curve recharts-area-area",d:j,fill:R.fill,stroke:"none",fillOpacity:.6}),e.jsx("path",{className:"recharts-curve recharts-area-curve",d:T,stroke:R.stroke,strokeWidth:R.strokeWidth??1,fill:"none"})]},R.dataKey)}),e.jsx(Is,{chart:t}),u&&l&&e.jsx("path",{className:"recharts-curve recharts-tooltip-cursor",stroke:((P=u.cursor)==null?void 0:P.stroke)??"#ccc",strokeWidth:1,fill:"none",pointerEvents:"none",d:`M${o(l.i)},${i.top}L${o(l.i)},${_}`}),l&&g.map(R=>{var w,T,M;return e.jsx("circle",{className:"recharts-dot",cx:o(l.i),cy:a(Number(F[l.i][R.dataKey])||0),r:((w=R.activeDot)==null?void 0:w.r)??4,fill:R.stroke,strokeWidth:((T=R.activeDot)==null?void 0:T.strokeWidth)??2,stroke:((M=R.activeDot)==null?void 0:M.stroke)??"#fff"},R.dataKey)}),e.jsx(qs,{chart:t,labels:b,width:E,height:A})]});return e.jsx(Hs,{width:E,height:A,svg:C,children:u&&m>0&&e.jsx($s,{tip:u,frame:i,at:l?{x:o(l.i),y:l.y}:null,label:l?b[l.i]:"",entries:l?g.map(R=>({name:R.name??R.dataKey,value:F[l.i][R.dataKey]})):[]})})}const Us={accent:"#4338CA",tint:"#EEEEFD",ring:"#DCDCFB",gradient:"linear-gradient(100deg, #8A1170 0%, #5B21B6 55%, #3730A3 100%)",series:["#4338CA","#059669","#DB2777"],bar:"linear-gradient(90deg, #3730A3, #4F46E5)"},dc={"student-lifecycle":{accent:"#6D28D9",tint:"#F3EEFF",ring:"#E4D8FD",gradient:"linear-gradient(100deg, #6D28D9 0%, #5B21B6 50%, #4338CA 100%)",series:["#7C3AED","#F59E0B","#0EA5E9"],bar:"linear-gradient(90deg, #6D28D9, #8B5CF6)"},academics:{accent:"#1D4ED8",tint:"#EEF4FF",ring:"#D6E4FF",gradient:"linear-gradient(100deg, #1E40AF 0%, #1D4ED8 50%, #0E7490 100%)",series:["#2563EB","#F59E0B","#14B8A6"],bar:"linear-gradient(90deg, #1D4ED8, #3B82F6)"},sports:{accent:"#C2410C",tint:"#FFF3EC",ring:"#FEDDC8",gradient:"linear-gradient(100deg, #C2410C 0%, #B91C1C 55%, #9D174D 100%)",series:["#EA580C","#0EA5E9","#7C3AED"],bar:"linear-gradient(90deg, #C2410C, #F97316)"},facilities:{accent:"#0F766E",tint:"#ECFAF8",ring:"#C9F0EA",gradient:"linear-gradient(100deg, #0F766E 0%, #0E7490 55%, #1E40AF 100%)",series:["#0D9488","#F59E0B","#6366F1"],bar:"linear-gradient(90deg, #0F766E, #14B8A6)"},"finance-operations":{accent:"#047857",tint:"#ECFDF5",ring:"#C9F2DF",gradient:"linear-gradient(100deg, #065F46 0%, #047857 50%, #0F766E 100%)",series:["#059669","#8B5CF6","#F59E0B"],bar:"linear-gradient(90deg, #047857, #10B981)"},"campus-life":{accent:"#B45309",tint:"#FFF8EB",ring:"#FCE7C3",gradient:"linear-gradient(100deg, #B45309 0%, #C2410C 50%, #BE185D 100%)",series:["#D97706","#6366F1","#0EA5E9"],bar:"linear-gradient(90deg, #B45309, #F59E0B)"},governance:{accent:"#3730A3",tint:"#EEF0FF",ring:"#DADDFE",gradient:"linear-gradient(100deg, #312E81 0%, #3730A3 50%, #4C1D95 100%)",series:["#4F46E5","#14B8A6","#F59E0B"],bar:"linear-gradient(90deg, #3730A3, #6366F1)"},support:{accent:"#0369A1",tint:"#EEF8FE",ring:"#CDEBFB",gradient:"linear-gradient(100deg, #075985 0%, #0369A1 50%, #0E7490 100%)",series:["#0284C7","#F97316","#8B5CF6"],bar:"linear-gradient(90deg, #0369A1, #0EA5E9)"}},Gs=n=>n&&dc[n]||Us,cc=n=>{var t;return Gs(n?(t=Je(n))==null?void 0:t.suiteId:void 0)},Ws=f.createContext(Us),mc=()=>f.useContext(Ws),Ys=({theme:n,children:t,className:s})=>e.jsx(Ws.Provider,{value:n,children:e.jsx("div",{className:s,style:{"--accent":n.accent,"--accent-tint":n.tint,"--accent-ring":n.ring,"--hero-gradient":n.gradient,"--accent-bar":n.bar},children:t})}),Ct={contentStyle:{backgroundColor:"#FFFFFF",border:"1px solid #E2E8F0",borderRadius:"8px",fontSize:"12px",color:"#12233F",boxShadow:"0 4px 12px rgba(15, 23, 42, 0.08)"},itemStyle:{color:"#334155"},labelStyle:{color:"#12233F",fontWeight:600}},Pt=({onClick:n,children:t})=>e.jsxs("button",{onClick:n,className:"inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:opacity-80 pt-0.5 whitespace-nowrap",children:[t,e.jsx(Fe,{className:"w-3.5 h-3.5"})]}),at=({title:n,subtitle:t,data:s,xKey:i,series:a,tooltipLabel:o,footer:m,className:p="",height:g=300})=>{const[u,k]=f.useState("bars"),h=f.useRef(null),l=rn(h),y=mc().series,v=A=>`g-${n.replace(/\W+/g,"-")}-${A}`,x=A=>o?o(String(A)):String(A),F=(A,b)=>[Number(A).toLocaleString("en-IN"),String(b)],E=e.jsxs(e.Fragment,{children:[e.jsx(Ds,{stroke:"#F1F5F9",vertical:!1}),e.jsx(Rs,{dataKey:i,stroke:"#64748B",fontSize:12,tickLine:!1,axisLine:{stroke:"#E2E8F0"}}),e.jsx(Ms,{stroke:"#64748B",fontSize:12,tickLine:!1,axisLine:!1,width:48,tickFormatter:A=>A.toLocaleString("en-IN")})]});return e.jsxs("section",{ref:h,className:`${z} flex flex-col eos-enter ${l?"is-in":""} ${p}`,children:[e.jsx(K,{title:n,subtitle:t,action:e.jsx("div",{className:"flex items-center gap-1 rounded-lg bg-[#F1F5F9] p-0.5 text-xs",role:"tablist","aria-label":"Chart view",children:["bars","trend"].map(A=>e.jsx("button",{role:"tab","aria-selected":u===A,onClick:()=>k(A),className:`px-2.5 py-1 rounded-md font-medium capitalize transition-colors ${u===A?"bg-white text-[#12233F] shadow-[0_1px_2px_rgba(15,23,42,0.08)]":"text-[#64748B] hover:text-[#12233F]"}`,children:A},A))})}),a.length>1&&e.jsx("div",{className:"px-5 flex flex-wrap items-center gap-4 text-[12px] text-[#475569]",children:a.map((A,b)=>e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx("span",{className:"w-2.5 h-2.5 rounded-sm",style:{background:y[b]}}),A.name]},A.key))}),e.jsx("div",{className:"px-5 pt-3 pb-4 flex-1",children:e.jsx("div",{className:"w-full",style:{height:g},role:"img","aria-label":`${u==="bars"?"Bar chart":"Trend"}: ${n}`,children:e.jsx(Zd,{width:"100%",height:"100%",children:u==="bars"?e.jsxs(rc,{data:s,margin:{top:8,right:8,left:0,bottom:0},barCategoryGap:"28%",barGap:4,children:[E,e.jsx(bn,{cursor:{fill:"rgba(148, 163, 184, 0.08)"},formatter:F,labelFormatter:x,...Ct}),a.map((A,b)=>e.jsx(tt,{dataKey:A.key,name:A.name,fill:y[b],radius:[4,4,0,0],maxBarSize:40,animationDuration:700},A.key))]}):e.jsxs(lc,{data:s,margin:{top:8,right:8,left:0,bottom:0},children:[e.jsx("defs",{children:a.map((A,b)=>e.jsxs("linearGradient",{id:v(A.key),x1:"0",y1:"0",x2:"0",y2:"1",children:[e.jsx("stop",{offset:"0%",stopColor:y[b],stopOpacity:.16}),e.jsx("stop",{offset:"100%",stopColor:y[b],stopOpacity:0})]},A.key))}),E,e.jsx(bn,{formatter:F,labelFormatter:x,...Ct}),a.map((A,b)=>e.jsx(st,{type:"monotone",dataKey:A.key,name:A.name,stroke:y[b],strokeWidth:2,fill:`url(#${v(A.key)})`,activeDot:{r:5,strokeWidth:2,stroke:"#FFFFFF"},animationDuration:700},A.key))]})})})}),m]})},it=({title:n,subtitle:t,items:s,action:i,footer:a,relativeToFirst:o,unit:m="",className:p=""})=>{var h;const g=o?((h=s[0])==null?void 0:h.count)||1:Math.max(1,...s.map(l=>l.count)),u=f.useRef(null),k=rn(u);return e.jsxs("section",{ref:u,className:`${z} flex flex-col eos-enter ${k?"is-in":""} ${p}`,style:{"--enter-delay":"120ms"},children:[e.jsx(K,{title:n,subtitle:t,action:i}),e.jsx("div",{className:"px-5 pt-1 pb-4 space-y-4 flex-1",children:s.map((l,y)=>{const v=Math.round(l.count/g*1e3)/10,x=250+y*160;return e.jsxs("div",{className:"space-y-1.5",children:[e.jsxs("div",{className:"flex items-center justify-between text-[13px] gap-3",children:[e.jsxs("span",{className:"text-[#334155] truncate inline-flex items-center gap-2",children:[l.color&&e.jsx("span",{className:"w-2 h-2 rounded-full flex-shrink-0",style:{background:l.color},"aria-hidden":!0}),l.label]}),e.jsxs("span",{className:"whitespace-nowrap",children:[e.jsxs("span",{className:"font-semibold text-[#12233F] tabular-nums",children:[e.jsx(_e,{end:l.count,active:k,duration:1e3,delay:x}),m]}),o&&e.jsxs("span",{className:"text-[11px] text-[#64748B] ml-1.5 tabular-nums",style:{opacity:k?1:0,transition:`opacity 400ms ease ${x+300}ms`},children:[v,"%"]})]})]}),e.jsx("div",{className:"w-full h-1.5 bg-[#F1F5F9] rounded-full overflow-hidden",children:e.jsx("div",{className:`h-full rounded-full eos-fill eos-sheen ${k?"is-in":""}`,style:{width:k?`${v}%`:0,backgroundImage:l.color?`linear-gradient(90deg, ${l.color}99, ${l.color})`:"var(--accent-bar)",transitionDelay:`${x}ms`,"--sheen-delay":`${x+900}ms`}})})]},l.label)})}),a&&e.jsxs("div",{className:"px-5 py-3 border-t border-[#F1F5F9] flex items-center justify-between text-xs",children:[e.jsx("span",{className:"text-[#475569]",children:a.label}),e.jsx("span",{className:"font-semibold text-[#12233F]",children:a.value})]})]})},pc={Urgent:"text-[#B91C1C]",Pending:"text-[#8A4F00]",Review:"text-[#475569]",Approved:"text-[#126B3D]"},uc=({items:n,onOpen:t})=>e.jsxs("section",{className:z,children:[e.jsx(K,{title:"Action Required",subtitle:`${n.length} items awaiting your decision`}),e.jsx("ul",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:n.map(s=>e.jsx("li",{children:e.jsxs("button",{onClick:()=>t(s),className:"w-full text-left px-5 py-3 flex items-start justify-between gap-4 hover:bg-[#F6F8FB] group",children:[e.jsxs("div",{className:"min-w-0",children:[e.jsxs("div",{className:"flex items-center gap-2 text-[11px]",children:[e.jsx("span",{className:"font-mono text-[#475569]",children:s.ref}),e.jsx("span",{className:"text-[#CBD5E1]",children:"·"}),e.jsx("span",{className:"text-[#475569]",children:s.type}),e.jsx("span",{className:`font-medium ${pc[s.urgency]}`,children:s.urgency})]}),e.jsx("p",{className:"text-[13px] font-medium text-[#12233F] mt-0.5 truncate",children:s.title}),e.jsx("p",{className:"text-xs text-[#64748B] truncate",children:s.description})]}),e.jsxs("div",{className:"flex items-center gap-2 flex-shrink-0 pt-0.5",children:[e.jsx("span",{className:"text-[11px] text-[#64748B] whitespace-nowrap",children:s.time}),e.jsx(Fe,{className:"w-3.5 h-3.5 text-[#64748B] group-hover:text-[#DC3545]"})]})]})},s.id))})]}),Rt={urgent:{fg:"#B91C1C",bg:"#FEF2F2"},pending:{fg:"#8A4F00",bg:"#FEF3E2"},normal:{fg:"#475569",bg:"#F1F5F9"}},gc={urgent:"Urgent",pending:"Pending",normal:"Open"};function zs({value:n,options:t,onChange:s,label:i}){return e.jsx("div",{className:"flex items-center gap-1 rounded-lg bg-[#F1F5F9] p-0.5 text-xs",role:"tablist","aria-label":i,children:t.map(([a,o])=>e.jsx("button",{role:"tab","aria-selected":n===a,onClick:()=>s(a),className:`px-2.5 py-1 rounded-md font-medium capitalize transition-colors ${n===a?"bg-white text-[#12233F] shadow-[0_1px_2px_rgba(15,23,42,0.08)]":"text-[#64748B] hover:text-[#12233F]"}`,children:o},a))})}const hc=({rows:n,action:t,className:s=""})=>{const[i,a]=f.useState("all"),o=f.useRef(null),m=rn(o),p=n.filter(h=>i==="all"||h.level===i),g=n.reduce((h,l)=>h+l.count,0),u=p.reduce((h,l)=>h+l.count,0),k=Math.max(1,...n.map(h=>h.count));return e.jsxs("section",{ref:o,className:`${z} flex flex-col eos-enter ${m?"is-in":""} ${s}`,children:[e.jsx(K,{title:"Action Required",subtitle:i==="all"?`${g} items awaiting decision`:`${u} of ${g} items · ${i}`,action:t??e.jsx(zs,{label:"Filter queues",value:i,onChange:a,options:[["all","All"],["urgent","Urgent"],["pending","Pending"]]})}),e.jsxs("ul",{className:`px-2 pb-2 flex-1 eos-reveal ${m?"is-in":""}`,children:[p.map((h,l)=>{const y=h.tone??Rt[h.level],v=Rt[h.level],x=h.icon??Fe;return e.jsx("li",{style:{"--i":l},children:e.jsxs("button",{onClick:h.onOpen,className:"w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-[#F6F8FB] group",children:[e.jsx("span",{className:"w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 eos-pop-in",style:{background:y.bg,color:y.fg},"aria-hidden":!0,children:e.jsx(x,{className:"w-4 h-4"})}),e.jsxs("span",{className:"flex-1 min-w-0",children:[e.jsx("span",{className:"block text-[13px] text-[#12233F] truncate",children:h.label}),e.jsx("span",{className:"block mt-1 h-1.5 w-full bg-[#F1F5F9] rounded-full overflow-hidden",children:e.jsx("span",{className:"block h-full rounded-full eos-fill",style:{width:m?`${h.count/k*100}%`:0,background:y.fg,transitionDelay:`${350+l*110}ms`}})})]}),e.jsx("span",{className:"text-[11px] font-medium px-2 py-0.5 rounded-full",style:{background:v.bg,color:v.fg},children:gc[h.level]}),e.jsx("span",{className:"w-8 text-right text-[14px] font-semibold text-[#12233F] tabular-nums",children:h.count}),e.jsx(Fe,{className:"w-3.5 h-3.5 text-[#CBD5E1] group-hover:text-[#DC3545]"})]})},h.label)}),p.length===0&&e.jsxs("li",{className:"px-3 py-8 text-center text-xs text-[#64748B]",children:["Nothing ",i," right now."]})]},i)]})},fc=864e5,yc=()=>{const n=new Date;return n.setHours(0,0,0,0),n},Rn=n=>Math.round((new Date(`${n}T00:00:00`).getTime()-yc().getTime())/fc),bc=n=>n<=0?"Today":n===1?"Tomorrow":`In ${n} days`,xc=({items:n,className:t=""})=>{const[s,i]=f.useState("all"),a=f.useRef(null),o=rn(a),m=[...n].sort((g,u)=>g.date.localeCompare(u.date)).filter(g=>Rn(g.date)>=0),p=m.filter(g=>{const u=Rn(g.date);return s==="all"||(s==="week"?u<=7:u>7)});return e.jsxs("section",{ref:a,className:`${z} flex flex-col eos-enter ${o?"is-in":""} ${t}`,style:{"--enter-delay":"120ms"},children:[e.jsx(K,{title:"Upcoming",subtitle:`Next two weeks · ${m.length} scheduled`,action:e.jsx(zs,{label:"Filter upcoming",value:s,onChange:i,options:[["all","All"],["week","This week"],["later","Later"]]})}),e.jsxs("ul",{className:`px-5 pb-3 flex-1 divide-y divide-[#F1F5F9] eos-reveal ${o?"is-in":""}`,children:[p.map((g,u)=>{const k=new Date(`${g.date}T00:00:00`),h=Rn(g.date),l=g.tone??{fg:"var(--accent)",bg:"var(--accent-tint)"},y=h<=2,v=e.jsxs(e.Fragment,{children:[e.jsxs("div",{className:"w-11 flex-shrink-0 text-center rounded-lg py-1",style:{background:l.bg,boxShadow:`inset 0 0 0 1px ${l.fg}33`},children:[e.jsx("div",{className:"text-[15px] leading-none font-bold tabular-nums",style:{color:l.fg},children:k.getDate().toString().padStart(2,"0")}),e.jsx("div",{className:"text-[10px] mt-0.5 font-medium uppercase text-[#64748B]",children:k.toLocaleDateString("en-GB",{month:"short"})})]}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsx("p",{className:"text-[13px] font-medium text-[#12233F] truncate",children:g.title}),e.jsx("p",{className:"text-xs text-[#64748B] truncate",children:g.meta})]}),e.jsx("span",{className:"text-[11px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap eos-slide-in",style:y?{background:"#FEF2F2",color:"#B91C1C"}:{background:l.bg,color:l.fg},title:g.category,children:bc(h)})]});return e.jsx("li",{style:{"--i":u},children:g.onOpen?e.jsxs("button",{onClick:g.onOpen,className:"w-full flex items-center gap-4 py-2.5 text-left rounded-lg hover:bg-[#F6F8FB] group",children:[v,e.jsx(Fe,{className:"w-3.5 h-3.5 text-[#CBD5E1] group-hover:text-[#DC3545]"})]}):e.jsx("div",{className:"flex items-center gap-4 py-2.5",children:v})},g.date+g.title)}),p.length===0&&e.jsxs("li",{className:"py-8 text-center text-xs text-[#64748B]",children:["Nothing scheduled ",s==="week"?"this week":"later","."]})]},s)]})},vc={"finance-staff":{icon:$n,bg:"#EAF6EC",fg:"#15803D"},"examination-staff":{icon:tn,bg:"#EEEEFD",fg:"#4338CA"},"org-admin":{icon:ze,bg:"#F3EEFF",fg:"#6D28D9"},"super-admin":{icon:ze,bg:"#F3EEFF",fg:"#6D28D9"},"department-admin":{icon:Ke,bg:"#FFF1E6",fg:"#C2410C"},coach:{icon:Ke,bg:"#FFF1E6",fg:"#C2410C"},"support-staff":{icon:Nn,bg:"#E8F4FD",fg:"#0369A1"},faculty:{icon:Yn,bg:"#EAF1FF",fg:"#1D4ED8"},governance:{icon:Kn,bg:"#FDECEC",fg:"#C2353F"},facility:{icon:Me,bg:"#ECFAF8",fg:"#0F766E"},system:{icon:or,bg:"#F1F5F9",fg:"#475569"}},wc=n=>vc[n],kc={Success:{cls:"bg-[#EEF7F1] text-[#126B3D] ring-[#CDE8D8]",icon:Z},Warning:{cls:"bg-[#FEF3E2] text-[#8A4F00] ring-[#FBE3BD]",icon:Ze},Failed:{cls:"bg-[#FEF2F2] text-[#B91C1C] ring-[#FECACA]",icon:ms}},Ks=({items:n,subtitle:t="Sample events",action:s})=>e.jsxs("section",{className:z,children:[e.jsx(K,{title:e.jsxs("span",{className:"inline-flex items-center gap-2.5",children:[e.jsx("span",{className:"w-7 h-7 rounded-lg bg-[var(--accent-tint)] text-[var(--accent)] flex items-center justify-center",children:e.jsx(In,{className:"w-4 h-4"})}),"Recent Activity",e.jsx("span",{className:"inline-flex items-center gap-1.5 rounded-full bg-[#F1F5F9] px-2 py-0.5 text-[10.5px] font-semibold text-[#475569]",children:"Sample"})]}),subtitle:t,action:s}),e.jsx("ul",{className:"relative px-3 pb-3",children:n.map((i,a)=>{const o=i.tone??{icon:In,bg:"var(--accent-tint)",fg:"var(--accent)"},m=o.icon,p=kc[i.status],g=p.icon,u=a===n.length-1;return e.jsxs("li",{className:"group relative flex items-center gap-4 rounded-lg px-2 py-2.5 transition-all duration-200 hover:bg-[#F8FAFC] hover:translate-x-0.5 animate-fade-up",style:{animationDelay:`${120+a*70}ms`},children:[e.jsx("span",{className:"hidden sm:block w-20 flex-shrink-0 text-right text-[12px] font-medium text-[#64748B] tabular-nums",children:i.time}),e.jsxs("span",{className:"relative flex-shrink-0 self-stretch flex items-center",children:[!u&&e.jsx("span",{"aria-hidden":!0,className:"absolute left-1/2 top-1/2 h-[calc(100%+20px)] w-px -translate-x-1/2 bg-[#E6EAF0]"}),e.jsx("span",{className:"relative z-10 w-8 h-8 rounded-full ring-4 ring-white flex items-center justify-center transition-transform duration-200 group-hover:scale-110",style:{backgroundColor:o.bg,color:o.fg},children:e.jsx(m,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsx("p",{className:"text-[13.5px] font-medium text-[#12233F] truncate",children:i.title}),e.jsx("p",{className:"text-xs text-[#64748B] truncate",children:i.meta})]}),e.jsxs("span",{className:`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-md ring-1 flex-shrink-0 ${p.cls}`,children:[e.jsx(g,{className:"w-3.5 h-3.5"}),i.status]})]},i.id)})})]}),wn="pending_approval",kn="pending_verification",Qs=n=>Be(`/tenancy/admin/organisations?status=${n}`),_c=()=>Qs(wn),jc=()=>Qs(kn),Fc=async()=>{const[n,t]=await Promise.all([_c(),jc()]);return[...n,...t].sort((s,i)=>(i.created_at??"").localeCompare(s.created_at??""))},Nc=n=>Be(`/tenancy/admin/organisations/${encodeURIComponent(n)}`),Sc=(n,t)=>{const s=t==null?void 0:t.trim();return Be(`/tenancy/admin/organisations/${encodeURIComponent(n)}/approve`,{method:"POST",json:s?{reason:s}:{}})},Ec=(n,t)=>{const s=t.trim();return s?Be(`/tenancy/admin/organisations/${encodeURIComponent(n)}/status`,{method:"PUT",json:{status:"archived",reason:s}}):Promise.reject(new Error("A reason is required to reject an organisation."))},Mn=n=>Re[n]?Qe(Re[n]):n,Dn=n=>n?new Date(n).toLocaleDateString("en-IN",{day:"numeric",month:"short",year:"numeric"}):"–",Ac=500,On="Your session has expired. Sign in again.",Cc="Couldn't reach the service. Please try again.",mn="inline-flex items-center gap-1 font-medium px-2 py-0.5 rounded bg-[#F1F5F9]",Mt=({status:n})=>n===wn?e.jsx("span",{className:`${mn} text-[#7E22CE]`,children:"Awaiting approval"}):n===kn?e.jsx("span",{className:`${mn} text-[#64748B]`,children:"Waiting for email verification"}):e.jsx("span",{className:`${mn} text-[#475569]`,children:n}),Dt=({title:n,onRetry:t,children:s})=>e.jsxs("div",{role:"alert",className:"p-4 rounded-lg border border-[#E2E8F0] bg-[#F6F8FB] text-xs space-y-3",children:[e.jsx("div",{className:"font-semibold text-[#B91C1C]",children:n}),e.jsx("p",{className:"text-[#475569]",children:s}),e.jsx("button",{type:"button",className:ae,onClick:t,children:"Try again"})]}),Pc=({onCountChange:n,onNotify:t,onSessionExpired:s,refreshKey:i=0})=>{var S;const a=f.useId(),[o,m]=f.useState("loading"),[p,g]=f.useState(""),[u,k]=f.useState([]),[h,l]=f.useState(""),[y,v]=f.useState(null),[x,F]=f.useState(null),[E,A]=f.useState("loading"),[b,_]=f.useState(""),[C,L]=f.useState(null),[P,R]=f.useState(""),[w,T]=f.useState(!1),[M,j]=f.useState(null),O=f.useRef(null),H=f.useRef(null),oe=f.useRef(null),J=f.useRef(0),U=f.useRef(s);U.current=s;const V=f.useCallback(async()=>{var D;m("loading");try{const q=await Fc();k(q),m("ready"),n==null||n(q.filter(Y=>Y.status===wn).length)}catch(q){const Y=q instanceof Oe&&q.status===401;g(Y?On:"The list of organisations awaiting approval couldn't be loaded."),m("error"),Y&&((D=U.current)==null||D.call(U))}},[n]);f.useEffect(()=>{V()},[V,i]);const te=async(D,q)=>{var ce;const Y=++J.current;O.current=q,v(D),F(null),A("loading");try{const ge=await Nc(D.id);if(Y!==J.current)return;F(ge),A("ready")}catch(ge){if(Y!==J.current)return;const rt=ge instanceof Oe&&ge.status===401;_(rt?On:"Its details couldn't be loaded. You can still close this panel."),A("error"),rt&&((ce=U.current)==null||ce.call(U))}},G=f.useCallback(()=>{var D;J.current++,v(null),F(null),L(null),j(null),R(""),(D=O.current)==null||D.focus()},[]),ee=f.useCallback(()=>{L(null),j(null)},[]),pe=D=>{R(""),j(null),L(D)};f.useEffect(()=>{if(!y)return;const D=q=>{q.key!=="Escape"||w||(C?ee():G())};return document.addEventListener("keydown",D),()=>document.removeEventListener("keydown",D)},[y,C,w,ee,G]),f.useEffect(()=>{var D;y&&!C&&((D=H.current)==null||D.focus())},[y,C]),f.useEffect(()=>{var D;C&&((D=oe.current)==null||D.focus())},[C]);const we=async()=>{var Y;if(!y||!C||w)return;const D=P.trim();if(C==="reject"&&!D){j("Give a reason for rejecting this organisation.");return}T(!0),j(null);const q=y.name;try{C==="approve"?await Sc(y.id,D):await Ec(y.id,D),G(),t(C==="approve"?`${q} approved. Its administrator can now sign in.`:`${q} rejected. Its registration is archived.`),await V()}catch(ce){const ge=ce instanceof Oe?ce.status:0;ge===409?(G(),t(`${q} is no longer awaiting approval.`),await V()):ge===404?(G(),t(`${q} no longer exists.`),await V()):ge===401?(j(On),(Y=U.current)==null||Y.call(U)):j(ge===403?`You don't have permission to ${C} organisations.`:Cc)}finally{T(!1)}},ue=h.trim().toLowerCase(),le=ue?u.filter(D=>D.name.toLowerCase().includes(ue)||D.slug.toLowerCase().includes(ue)):u,de=E==="ready"&&(x==null?void 0:x.status)===wn,I=E==="ready"&&x&&!de?x.status===kn?"Waiting for the administrator to verify their email.":"No longer awaiting approval.":null,$=C==="reject";return e.jsxs("section",{className:z,"aria-labelledby":`${a}-title`,children:[e.jsx(K,{title:e.jsx("span",{id:`${a}-title`,children:"Organisations awaiting approval"}),subtitle:"Verified registrations can be approved or rejected; unverified ones wait for the administrator's email.",action:o==="ready"&&u.length>0?e.jsxs("div",{className:"relative",children:[e.jsx(ye,{className:"w-4 h-4 text-[#475569] absolute left-3 top-2.5"}),e.jsx("input",{type:"text","aria-label":"Search organisations awaiting approval",placeholder:"Search by name or short name...",value:h,onChange:D=>l(D.target.value),className:"w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"})]}):void 0}),o==="loading"&&e.jsx("p",{className:"py-8 text-center text-[#475569] text-xs",role:"status",children:"Loading organisations…"}),o==="error"&&e.jsx("div",{className:"p-4",children:e.jsx(Dt,{title:"Couldn't load the approval queue",onRetry:()=>void V(),children:p})}),o==="ready"&&e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-3 px-4",children:"Organisation"}),e.jsx("th",{className:"py-3 px-4",children:"Academy type"}),e.jsx("th",{className:"py-3 px-4",children:"Status"}),e.jsx("th",{className:"py-3 px-4",children:"Registered"}),e.jsx("th",{className:"py-3 px-4 text-right",children:"Actions"})]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9] text-[#12233F]",children:le.length===0?e.jsx("tr",{children:e.jsx("td",{colSpan:5,className:"py-8 text-center text-[#475569]",children:u.length===0?"No organisations are waiting for approval.":"No organisations match the search."})}):le.map(D=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors",children:[e.jsxs("td",{className:"py-3 px-4",children:[e.jsx("div",{className:"font-semibold text-[#12233F]",children:D.name}),e.jsx("div",{className:"text-[11px] text-[#64748B] font-mono",children:D.slug})]}),e.jsx("td",{className:"py-3 px-4",children:e.jsx("span",{className:`${mn} text-[#7E22CE]`,children:Mn(D.academy_type)})}),e.jsx("td",{className:"py-3 px-4",children:e.jsx(Mt,{status:D.status})}),e.jsx("td",{className:"py-3 px-4 text-[#475569]",children:Dn(D.created_at)}),e.jsx("td",{className:"py-3 px-4 text-right",children:e.jsx("button",{type:"button",className:ae,"aria-label":`Review ${D.name}`,onClick:q=>void te(D,q.currentTarget),children:"Review"})})]},D.id))})]})}),y&&la.createPortal(e.jsxs("div",{className:"fixed inset-0 z-50 overflow-hidden",children:[e.jsx("div",{className:"absolute inset-0 bg-[#12233F]/50 backdrop-blur-xs transition-opacity",onClick:()=>!w&&G()}),e.jsx("div",{className:"fixed inset-y-0 right-0 max-w-full flex pl-10",children:e.jsxs("div",{ref:H,role:"dialog","aria-modal":"true","aria-labelledby":`${a}-drawer-title`,tabIndex:-1,className:"w-screen max-w-md bg-[#FFFFFF] shadow-2xl border-l border-[#E2E8F0] flex flex-col focus:outline-none",children:[e.jsxs("div",{className:"p-5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]",children:[e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx(Me,{className:"w-4 h-4 text-[#7E22CE]"}),e.jsxs("span",{id:`${a}-drawer-title`,className:"text-sm font-bold text-[#12233F]",children:["Review ",y.name]})]}),e.jsx("button",{type:"button","aria-label":"Close",onClick:G,disabled:w,className:"p-1 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#FFFFFF]",children:e.jsx(ie,{className:"w-5 h-5"})})]}),e.jsxs("div",{className:"flex-1 overflow-y-auto p-6 space-y-6",children:[E==="loading"&&e.jsx("p",{className:"text-xs text-[#475569]",role:"status",children:"Loading details…"}),E==="error"&&e.jsx(Dt,{title:"Couldn't load this organisation",onRetry:()=>O.current&&void te(y,O.current),children:b}),E==="ready"&&x&&e.jsxs("div",{className:"space-y-3",children:[e.jsx("h4",{className:"text-xs font-bold uppercase tracking-wider text-[#475569]",children:"Registration"}),e.jsx("dl",{className:"p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2.5 text-xs",children:[["Organisation",x.name],["Short name",x.slug],["Academy type",Mn(x.academy_type)],...x.requested_academy_type?[["Requested package change",Mn(x.requested_academy_type)]]:[],["Country",x.country||"–"],["Plan",y.plan??"–"],["Trial ends",Dn(y.trial_ends_at??((S=x.entitlement)==null?void 0:S.trial_ends_at))],["Registered",Dn(x.created_at)],["Status",e.jsx(Mt,{status:x.status})],["Email verified",x.status===kn?"No":"Yes"],["Administrator email",x.admin_email??"Not available from the API yet"]].map(([D,q])=>e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsxs("dt",{className:"text-[#475569]",children:[D,":"]}),e.jsx("dd",{className:"font-medium text-[#12233F]",children:q})]},D))})]})]}),e.jsxs("div",{className:"p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-end gap-2",children:[I&&e.jsx("span",{className:"text-xs text-[#64748B] flex-1",children:I}),e.jsx("button",{type:"button",onClick:G,disabled:w,className:ae,children:"Close"}),e.jsxs("button",{type:"button",onClick:()=>pe("reject"),disabled:!de,className:Nt,children:[e.jsx(ie,{className:"w-3.5 h-3.5"}),"Reject"]}),e.jsxs("button",{type:"button",onClick:()=>pe("approve"),disabled:!de,className:je,children:[e.jsx(Z,{className:"w-3.5 h-3.5"}),"Approve"]})]})]})}),C&&e.jsx("div",{className:"fixed inset-0 z-50 bg-[#12233F]/40 backdrop-blur-xs flex items-center justify-center p-4",children:e.jsxs("div",{ref:oe,role:"dialog","aria-modal":"true","aria-labelledby":`${a}-confirm-title`,"aria-describedby":`${a}-confirm-text`,tabIndex:-1,className:"w-full max-w-md bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden focus:outline-none",children:[e.jsxs("div",{className:"p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]",children:[e.jsxs("h3",{id:`${a}-confirm-title`,className:"text-sm font-bold text-[#12233F]",children:[$?"Reject":"Approve"," ",y.name,"?"]}),e.jsx("button",{type:"button","aria-label":"Cancel",onClick:ee,disabled:w,className:"text-[#475569] hover:text-[#12233F]",children:e.jsx(ie,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"p-5 space-y-4 text-xs",children:[e.jsx("p",{id:`${a}-confirm-text`,className:"text-[#475569]",children:$?"The registration is archived and its administrator cannot sign in.":"The organisation becomes active and its administrator can sign in."}),e.jsxs("div",{children:[e.jsx("label",{htmlFor:`${a}-reason`,className:"block font-semibold text-[#12233F] mb-1",children:$?"Reason (required)":"Reason (optional)"}),e.jsx("textarea",{id:`${a}-reason`,value:P,maxLength:Ac,required:$,onChange:D=>R(D.target.value),disabled:w,className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"})]}),M&&e.jsx("div",{role:"alert",className:"p-3 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[11px] text-[#B91C1C]",children:M}),e.jsxs("div",{className:"flex justify-end gap-2 pt-2",children:[e.jsx("button",{type:"button",onClick:ee,disabled:w,className:"px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569]",children:"Cancel"}),e.jsx("button",{type:"button",onClick:()=>void we(),disabled:w||$&&!P.trim(),"aria-busy":w||void 0,className:$?Nt:"px-4 py-1.5 rounded-lg bg-[#F65B66] text-white font-semibold hover:bg-[#E9505C]",children:w?$?"Rejecting…":"Approving…":$?"Reject":"Approve"})]})]})]})})]}),document.body)]})},Rc=[{key:"academics",name:"Academic"},{key:"sportsQuota",name:"Sports quota"}],fe={admissions:{fg:"#7E22CE",bg:"#F3E8FF"},exams:{fg:"#4338CA",bg:"#EEEEFD"},workflow:{fg:"#6256C9",bg:"#EFEDFB"},finance:{fg:"#15803D",bg:"#EAF6EC"},governance:{fg:"#DC2626",bg:"#FEF2F2"},sports:{fg:"#C2410C",bg:"#FFF1E6"}},Mc=[{inDays:1,title:"Admission review",meta:"Admissions committee · Batch 2026",category:"Admissions",tone:fe.admissions,to:"/admissions"},{inDays:5,title:"Examination schedule",meta:"End-semester timetable release",category:"Exam",tone:fe.exams,to:"/modules/examinations"},{inDays:8,title:"Finance reconciliation",meta:"Autumn fee ledger close",category:"Finance",tone:fe.finance,to:"/modules/fees-accounts"},{inDays:12,title:"Inter-university athletics",meta:"Tournament & events · Main campus",category:"Sports",tone:fe.sports,to:"/modules/tournament-events"}],Dc=n=>{const t=new Date;return t.setDate(t.getDate()+n),`${t.getFullYear()}-${String(t.getMonth()+1).padStart(2,"0")}-${String(t.getDate()).padStart(2,"0")}`},Tn=({children:n})=>e.jsxs("span",{className:"inline-flex items-center",children:[e.jsx(os,{className:"w-3 h-3 mr-0.5"}),n]}),Oc=n=>n<12?"Good morning":n<17?"Good afternoon":"Good evening",Tc=()=>{const n=Zn(),{session:t,preview:s,signOut:i}=me(),a=(t==null?void 0:t.me.name)||(t==null?void 0:t.me.email)||"Administrator",o=!!(t!=null&&t.me.is_super_admin)&&!s,[m,p]=f.useState(null),g=Fn(),[u,k]=f.useState(null),[h,l]=f.useState(0),[y,v]=f.useState(!1),x=f.useRef(null);f.useEffect(()=>{const C=L=>{x.current&&!x.current.contains(L.target)&&v(!1)};return document.addEventListener("mousedown",C),()=>document.removeEventListener("mousedown",C)},[]);const F=C=>{k(C),setTimeout(()=>k(null),3e3)},E=[{label:"Generate report",icon:dr,run:()=>F("Reports need platform/reporting, which is not built yet")},{label:"Create user",icon:Mr,run:()=>g("/users?new=1")},{label:"New announcement",icon:wr,run:()=>F("Announcements need platform/notification, which is not built yet")},{label:"Refresh metrics",icon:Er,run:()=>{l(C=>C+1),F(o?"Approval queue reloaded":"Sample figures reloaded")}}],A=[{label:"Total Students",icon:sn,value:e.jsx(_e,{end:3842},h),delta:e.jsx(Tn,{children:"+4.8%"}),note:"vs last session",to:"/modules/student-information",viz:e.jsx(Hd,{values:[3420,3510,3560,3640,3700,3790,3842],colors:["#6256C9","#315EA8","#159A72","#22A06B","#E89A35","#E45B67","#315EA8"]})},{label:"Active Athletes",icon:Ke,value:e.jsx(_e,{end:428},h),delta:e.jsx(Tn,{children:"+8.2%"}),note:"16 disciplines",to:"/modules/athlete-performance",viz:e.jsx(Ud,{delay:600,slices:[{value:30,color:"#315EA8"},{value:20,color:"#159A72"},{value:18,color:"#E89A35"},{value:14,color:"#E45B67"},{value:18,color:"#6256C9"}]})},o?{label:"Pending Approvals",icon:An,value:m===null?"–":e.jsx(_e,{end:m},`orgs-${m}`),note:"Organisations awaiting approval"}:{label:"Pending Approvals",icon:An,value:e.jsx(_e,{end:38},h),delta:"12 urgent",deltaTone:"alert",to:"/admissions",viz:e.jsx(Yd,{delay:300,bars:[{value:12,color:"#E45B67"},{value:10,color:"#6256C9"},{value:8,color:"#E89A35"},{value:5,color:"#315EA8"},{value:3,color:"#159A72"}]})},{label:"Fee Collection",icon:$n,value:e.jsx(_e,{end:8.42,decimals:2,prefix:"₹",suffix:" Cr"},h),delta:e.jsx(Tn,{children:"+12.4%"}),note:"Autumn 2026",to:"/modules/fees-accounts",viz:e.jsx(Gd,{delay:900,colors:["#22A06B","#315EA8","#E89A35"],stacks:[[3.1,1.3,.7],[3.4,1.4,.8],[3.7,1.6,.9],[4,1.7,.9],[4.4,1.8,1.1],[4.7,2,1.2],[5,2.1,1.32]]})},{label:"Active Faculty",icon:is,value:e.jsx(_e,{end:312},h),delta:"96% rostered",deltaTone:"muted",accent:"navy",to:"/modules/hr-payroll",viz:e.jsx(Wd,{of:100,delay:450,slices:[{value:34,color:"#6256C9"},{value:26,color:"#315EA8"},{value:21,color:"#159A72"},{value:15,color:"#E89A35"}]})},{label:"Support Tickets",icon:Nn,value:e.jsx(_e,{end:24},h),delta:"Avg response 4.2h",deltaTone:"muted",accent:"orange",to:"/modules/helpdesk",viz:e.jsx(zd,{delay:1200,value:4.2/6,zones:[{to:.5,color:"#22A06B"},{to:.8333,color:"#E89A35"},{to:1,color:"#E45B67"}]})}],b=[{label:"Admission approvals",count:12,level:"urgent",icon:Ye,tone:fe.admissions,onOpen:()=>g("/admissions")},{label:"Other approvals",count:10,level:"pending",icon:An,tone:fe.workflow,onOpen:()=>g("/modules/workflow")},{label:"Examination approvals",count:8,level:"pending",icon:tn,tone:fe.exams,onOpen:()=>g("/modules/examinations")},{label:"Finance approvals",count:5,level:"pending",icon:$n,tone:fe.finance,onOpen:()=>g("/modules/fees-accounts")},{label:"Grievance cases",count:3,level:"normal",icon:Kn,tone:fe.governance,onOpen:()=>g("/modules/grievance")}],_=Mc.map(({inDays:C,to:L,...P})=>({...P,date:Dc(C),onOpen:()=>g(L)}));return e.jsxs("div",{className:"space-y-6",children:[u&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs",children:[e.jsx(Z,{className:"w-4 h-4 text-[#6FCF97]"}),e.jsx("span",{children:u})]}),e.jsx(ve,{title:"Dashboard",art:e.jsx(nt,{}),subtitle:e.jsxs(e.Fragment,{children:[e.jsxs("span",{className:"block text-[15px] text-[#12233F]",children:[Oc(new Date().getHours()),", ",e.jsx("span",{className:"font-semibold",children:a})]}),e.jsxs("span",{className:"block mt-0.5 text-[13px] text-[#64748B]",children:[n.name," · Academic Year 2026–27"]})]}),actions:e.jsxs(e.Fragment,{children:[e.jsxs("button",{onClick:()=>F("Student records need the student-information module, which is not built yet"),className:ae,children:[e.jsx(Dr,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),"Add Student"]}),e.jsxs("button",{onClick:()=>g("/admissions"),className:je,children:[e.jsx(Ye,{className:"w-3.5 h-3.5"}),"Review Admissions"]}),e.jsxs("div",{className:"relative",ref:x,children:[e.jsxs("button",{onClick:()=>v(C=>!C),"aria-haspopup":"menu","aria-expanded":y,className:ae,children:["More",e.jsx(en,{className:"w-3.5 h-3.5 text-[#64748B]"})]}),y&&e.jsx("div",{role:"menu",className:"absolute right-0 mt-1.5 w-48 rounded-lg bg-white border border-[#E2E8F0] shadow-lg py-1 z-20",children:E.map(({label:C,icon:L,run:P})=>e.jsxs("button",{role:"menuitem",onClick:()=>{v(!1),P()},className:"w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#12233F] hover:bg-[#F6F8FB]",children:[e.jsx(L,{className:"w-3.5 h-3.5 text-[#64748B]"}),C]},C))})]})]})}),e.jsx(xe,{stats:A,colorful:!0}),o&&e.jsx(Pc,{onCountChange:p,onNotify:F,onSessionExpired:()=>{i(),g("/login",{replace:!0})},refreshKey:h}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsx(at,{className:"lg:col-span-2 eos-lift",title:"Student Enrollment",subtitle:"Enrollment by academic year",data:Ad,xKey:"year",series:Rc,height:260,tooltipLabel:C=>`Academic year ${C}`}),e.jsx(it,{className:"eos-lift",title:"Admissions Overview",subtitle:"Batch 2026",relativeToFirst:!0,items:ks.map((C,L)=>({label:C.stage,count:C.count,color:ws[L]})),action:e.jsx(Pt,{onClick:()=>g("/admissions"),children:"View Admissions"}),footer:{label:"Overall acceptance",value:"37.8%"}})]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-2 gap-6",children:[e.jsx(hc,{rows:b,className:"eos-lift"}),e.jsx(xc,{items:_,className:"eos-lift"})]}),e.jsx(Ks,{items:vs.slice(0,5).map(C=>({id:C.id,time:C.timestamp,title:C.action,meta:`${C.user} · ${re(C.role)}`,status:C.status,tone:wc(C.role)})),action:e.jsx(Pt,{onClick:()=>g("/audit-logs"),children:"View all"})})]})},Bc=n=>{var t;return{id:n.id,name:n.name,email:n.email,role:n.roles[0]??"student",department:"–",status:"Active",lastLogin:"–",dataScope:((t=yn(n.roles[0]??""))==null?void 0:t.dataScope)??"Self"}},Lc=()=>{var $;const{session:n}=me(),{ROLES:t}=et(),s=!!(n!=null&&n.organisation),i=!(n!=null&&n.me.is_super_admin),[a]=Wt(),[o,m]=f.useState(s?[]:Sd),[p,g]=f.useState(""),[u,k]=f.useState(!1),h=f.useCallback(async()=>{if(s)try{m((await Be("/identity/users")).map(Bc))}catch(S){M(S instanceof Oe?`Could not load users: ${S.message}`:"Could not load users")}},[s]);f.useEffect(()=>{h()},[h]);const[l,y]=f.useState(""),[v,x]=f.useState("All"),[F,E]=f.useState("All"),[A,b]=f.useState("All"),[_,C]=f.useState(null),[L,P]=f.useState(!1),[R,w]=f.useState(!1);f.useEffect(()=>{a.get("new")==="1"&&i&&w(!0)},[a,i]);const[T,M]=f.useState(null),[j,O]=f.useState(""),[H,oe]=f.useState(""),[J,U]=f.useState("faculty"),[V,te]=f.useState("Physical Education"),G=S=>{M(S),setTimeout(()=>M(null),3e3)},ee=S=>{C(S),P(!0)},pe=()=>{P(!1),C(null)},we=S=>{m(D=>D.map(q=>{if(q.id===S){const Y=q.status==="Active"?"Suspended":"Active",ce={...q,status:Y};return(_==null?void 0:_.id)===S&&C(ce),G(`Preview only: ${q.name} shown as ${Y}; suspending users is not in the identity API yet`),ce}return q}))},ue=async S=>{var q;if(S.preventDefault(),!j||!H)return;if(s){k(!0);try{await Be("/identity/users",{method:"POST",json:{email:H,name:j,password:p,roles:[J]}}),await h(),w(!1),O(""),oe(""),g(""),G(`${j} can now sign in with ${H}`)}catch(Y){G(Y instanceof Oe?`Not created: ${Y.message}`:"Not created")}finally{k(!1)}return}const D={id:`USR-${1e3+o.length+1}`,name:j,email:H,role:J,department:V,status:"Active",lastLogin:"Never (New)",dataScope:((q=yn(J))==null?void 0:q.dataScope)??"Department"};m([D,...o]),w(!1),O(""),oe(""),g(""),G(`Preview only: ${D.name} added to this page, not saved`)},le=o.filter(S=>{const D=S.name.toLowerCase().includes(l.toLowerCase())||S.email.toLowerCase().includes(l.toLowerCase())||S.id.toLowerCase().includes(l.toLowerCase()),q=v==="All"||S.role===v,Y=F==="All"||S.department===F,ce=A==="All"||S.status===A;return D&&q&&Y&&ce}),de=["All",...Array.from(new Set(o.map(S=>S.role)))],I=["All",...Array.from(new Set(o.map(S=>S.department)))];return e.jsxs("div",{className:"space-y-6",children:[T&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs",children:[e.jsx(Z,{className:"w-4 h-4 text-[#126B3D]"}),e.jsx("span",{children:T})]}),e.jsx(ve,{title:"Users & Access",subtitle:s?"Users of your organisation, from platform/identity.":n!=null&&n.me.is_super_admin?"Sample directory. Users belong to organisations; a super admin works through organisation screens (not built yet).":"Sample directory (preview). Sign in as an organisation admin to see and add real users.",actions:i?e.jsxs("button",{onClick:()=>w(!0),className:je,children:[e.jsx(as,{className:"w-3.5 h-3.5"}),"Add User"]}):void 0}),e.jsx(xe,{stats:[{label:"Users",icon:sn,value:o.length.toLocaleString("en-IN"),note:s?"In your organisation":"Sample list"},{label:"Active",icon:ds,value:String(o.filter(S=>S.status==="Active").length),note:s?"Can sign in":"Sample list"},{label:"Pending",icon:nn,value:String(o.filter(S=>S.status==="Pending").length),note:"Not signed in yet"},{label:"Suspended",icon:Or,value:String(o.filter(S=>S.status==="Suspended").length),deltaTone:"alert",note:"Sample only: no suspend API yet"}]}),e.jsx("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs space-y-3",children:e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3",children:[e.jsxs("div",{className:"relative",children:[e.jsx(ye,{className:"w-4 h-4 text-[#475569] absolute left-3 top-2.5"}),e.jsx("input",{type:"text",placeholder:"Search by name, ID or email...",value:l,onChange:S=>y(S.target.value),className:"w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"})]}),e.jsx("div",{children:e.jsxs("select",{value:v,onChange:S=>x(S.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Roles"}),de.filter(S=>S!=="All").map(S=>e.jsx("option",{value:S,children:re(S)},S))]})}),e.jsx("div",{children:e.jsxs("select",{value:F,onChange:S=>E(S.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Departments"}),I.filter(S=>S!=="All").map(S=>e.jsx("option",{value:S,children:S},S))]})}),e.jsx("div",{children:e.jsxs("select",{value:A,onChange:S=>b(S.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Statuses"}),e.jsx("option",{value:"Active",children:"Active"}),e.jsx("option",{value:"Pending",children:"Pending"}),e.jsx("option",{value:"Suspended",children:"Suspended"})]})})]})}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden",children:[e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-3 px-4",children:"User ID"}),e.jsx("th",{className:"py-3 px-4",children:"Name"}),e.jsx("th",{className:"py-3 px-4",children:"Role"}),e.jsx("th",{className:"py-3 px-4",children:"Department"}),e.jsx("th",{className:"py-3 px-4",children:"Email"}),e.jsx("th",{className:"py-3 px-4",children:"Status"}),e.jsx("th",{className:"py-3 px-4",children:"Last Login"}),e.jsx("th",{className:"py-3 px-4 text-right",children:"Actions"})]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9] text-[#12233F]",children:le.length===0?e.jsx("tr",{children:e.jsx("td",{colSpan:8,className:"py-8 text-center text-[#475569]",children:"No university users match the applied filters."})}):le.map(S=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors cursor-pointer group",onClick:()=>ee(S),children:[e.jsx("td",{className:"py-3 px-4 font-mono font-medium text-[#7E22CE]",children:S.id}),e.jsxs("td",{className:"py-3 px-4",children:[e.jsx("div",{className:"font-semibold text-[#12233F]",children:S.name}),e.jsx("div",{className:"text-[11px] text-[#64748B] font-mono",children:S.employeeId})]}),e.jsx("td",{className:"py-3 px-4",children:e.jsx("span",{className:"inline-flex items-center gap-1 font-medium px-2 py-0.5 rounded bg-[#F1F5F9] text-[#7E22CE]",children:re(S.role)})}),e.jsx("td",{className:"py-3 px-4 text-[#475569]",children:S.department}),e.jsx("td",{className:"py-3 px-4 text-[#475569] font-mono text-[11px]",children:S.email}),e.jsx("td",{className:"py-3 px-4",children:e.jsxs("span",{className:`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${S.status==="Active"?"bg-[#16834B26] text-[#126B3D]":S.status==="Pending"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-current"}),S.status]})}),e.jsx("td",{className:"py-3 px-4 text-[#475569] whitespace-nowrap",children:S.lastLogin}),e.jsx("td",{className:"py-3 px-4 text-right",onClick:D=>D.stopPropagation(),children:e.jsx("button",{onClick:()=>ee(S),className:"px-2.5 py-1 rounded border border-[#E2E8F0] hover:border-[#9333EA] text-[#7E22CE] font-medium hover:bg-[#FFFFFF] text-[11px] transition-colors",children:"Details →"})})]},S.id))})]})}),e.jsxs("div",{className:"py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]",children:[e.jsxs("span",{children:["Showing ",e.jsx("strong",{className:"text-[#12233F]",children:le.length})," of"," ",e.jsx("strong",{className:"text-[#12233F]",children:o.length})," loaded staff records"]}),e.jsx("span",{className:"text-[11px]",children:"Sample data · identity lists and creates users today"})]})]}),L&&_&&e.jsxs("div",{className:"fixed inset-0 z-50 overflow-hidden",children:[e.jsx("div",{className:"absolute inset-0 bg-[#12233F]/50 backdrop-blur-xs transition-opacity",onClick:pe}),e.jsx("div",{className:"fixed inset-y-0 right-0 max-w-full flex pl-10",children:e.jsxs("div",{className:"w-screen max-w-md bg-[#FFFFFF] shadow-2xl border-l border-[#E2E8F0] flex flex-col",children:[e.jsxs("div",{className:"p-5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]",children:[e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx("span",{className:"font-mono text-xs px-2 py-0.5 rounded bg-[#7E22CE26] text-[#7E22CE] font-semibold",children:_.id}),e.jsx("span",{className:"text-sm font-bold text-[#12233F]",children:"User Profile & Scope"})]}),e.jsx("button",{onClick:pe,className:"p-1 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#FFFFFF]",children:e.jsx(ie,{className:"w-5 h-5"})})]}),e.jsxs("div",{className:"flex-1 overflow-y-auto p-6 space-y-6",children:[e.jsxs("div",{className:"flex items-center gap-4 pb-4 border-b border-[#F1F5F9]",children:[e.jsx("div",{className:"w-14 h-14 rounded-xl bg-[#7E22CE] text-white flex items-center justify-center font-bold text-lg shadow-sm",children:_.name.split(" ").map(S=>S[0]).slice(0,2).join("")}),e.jsxs("div",{children:[e.jsx("h3",{className:"text-base font-bold text-[#12233F]",children:_.name}),e.jsx("p",{className:"text-xs text-[#7E22CE] font-medium",children:re(_.role)}),e.jsxs("p",{className:"text-[10px] text-[#64748B] font-mono",children:["role: ",_.role," · ",(($=yn(_.role))==null?void 0:$.permissions.length)??0," permission keys"]}),e.jsx("p",{className:"text-[11px] text-[#475569]",children:_.department})]})]}),e.jsxs("div",{className:"space-y-3",children:[e.jsx("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]",children:"Institutional Details"}),e.jsxs("div",{className:"p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2.5 text-xs",children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Employee Code:"}),e.jsx("span",{className:"font-mono font-medium text-[#12233F]",children:_.employeeId})]}),e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Institutional Email:"}),e.jsx("span",{className:"font-mono text-[#7E22CE]",children:_.email})]}),e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Official Phone:"}),e.jsx("span",{className:"text-[#12233F]",children:_.phone})]}),e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Last Authenticated:"}),e.jsx("span",{className:"text-[#12233F]",children:_.lastLogin})]})]})]}),e.jsxs("div",{className:"space-y-2",children:[e.jsx("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]",children:"Data Scope (sample, not enforced)"}),e.jsxs("div",{className:"p-3.5 rounded-lg bg-[#7E22CE26]/50 border border-[#9333EA]/20 flex items-start gap-3",children:[e.jsx(be,{className:"w-4 h-4 text-[#7E22CE] mt-0.5"}),e.jsxs("div",{children:[e.jsxs("div",{className:"font-semibold text-xs text-[#7E22CE]",children:[_.dataScope," Scope"]}),e.jsx("p",{className:"text-[11px] text-[#475569] mt-0.5",children:_.dataScope==="Institution"?"Whole organisation. Row-level security today is per organisation only.":_.dataScope==="Department"?`Own department (${_.department}). Not enforced by the API yet.`:"Assigned records only. Not enforced by the API yet."})]})]})]}),e.jsxs("div",{className:"space-y-2",children:[e.jsx("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]",children:"Security Status"}),e.jsxs("div",{className:"p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2 text-xs",children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Two-Factor Authentication:"}),e.jsx("span",{className:"font-semibold px-2 py-0.5 rounded text-[10px] bg-[#F1F5F9] text-[#475569]",children:"Not available yet"})]}),e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Account Status:"}),e.jsx("span",{className:`font-semibold px-2 py-0.5 rounded text-[10px] ${_.status==="Active"?"bg-[#16834B26] text-[#126B3D]":_.status==="Pending"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:_.status})]})]})]})]}),e.jsx("div",{className:"p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] space-y-2",children:e.jsxs("div",{className:"grid grid-cols-2 gap-2",children:[e.jsx("button",{onClick:()=>{G("Password reset is not in the identity API yet")},className:"py-2 px-3 rounded-lg border border-[#E2E8F0] hover:bg-[#FFFFFF] text-xs font-medium text-[#12233F] transition-colors",children:"Reset Password"}),e.jsx("button",{onClick:()=>we(_.id),className:`py-2 px-3 rounded-lg text-xs font-medium transition-colors ${_.status==="Active"?"border border-[#DC262626] text-[#B91C1C] hover:bg-[#DC262626]/30":"border border-[#16834B26] text-[#126B3D] hover:bg-[#16834B26]/50"}`,children:_.status==="Active"?"Suspend User":"Activate User"})]})})]})})]}),R&&e.jsx("div",{className:"fixed inset-0 z-50 bg-[#12233F]/40 backdrop-blur-xs flex items-center justify-center p-4",children:e.jsxs("div",{className:"w-full max-w-md bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden",children:[e.jsxs("div",{className:"p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]",children:[e.jsx("h3",{className:"text-sm font-bold text-[#12233F]",children:"Create Institutional User"}),e.jsx("button",{onClick:()=>w(!1),className:"text-[#475569] hover:text-[#12233F]",children:e.jsx(ie,{className:"w-4 h-4"})})]}),e.jsxs("form",{onSubmit:ue,className:"p-5 space-y-4 text-xs",children:[e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Full Name"}),e.jsx("input",{type:"text",required:!0,value:j,onChange:S=>O(S.target.value),placeholder:"e.g. Gurpreet Singh",className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"})]}),e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Institutional Email"}),e.jsx("input",{type:"email",required:!0,value:H,onChange:S=>oe(S.target.value),placeholder:"e.g. name@your-institution.edu",className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"})]}),e.jsxs("div",{className:"grid grid-cols-2 gap-3",children:[e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Assigned Role"}),e.jsx("select",{value:J,onChange:S=>U(S.target.value),className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]",children:t.filter(S=>S.id!=="super-admin").map(S=>e.jsx("option",{value:S.id,children:S.title},S.id))})]}),e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Department"}),e.jsxs("select",{value:V,onChange:S=>te(S.target.value),className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]",children:[e.jsx("option",{value:"Sports Science & Biomechanics",children:"Sports Science"}),e.jsx("option",{value:"Athletics & Track",children:"Athletics"}),e.jsx("option",{value:"Physical Education",children:"Physical Education"}),e.jsx("option",{value:"Finance & Accounts",children:"Finance"}),e.jsx("option",{value:"Computer Science & AI",children:"Computer Science"})]})]})]}),e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Initial Password"}),e.jsx("input",{type:"password",required:!0,minLength:8,value:p,onChange:S=>g(S.target.value),placeholder:"At least 8 characters",className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"})]}),e.jsx("div",{className:"p-3 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[11px] text-[#475569]",children:s?"Created in your organisation through platform/identity. Share the password with the user; email invitations and 2FA are not available yet.":"Preview: the user is added to this page only and not saved."}),e.jsxs("div",{className:"flex justify-end gap-2 pt-2",children:[e.jsx("button",{type:"button",onClick:()=>w(!1),className:"px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569]",children:"Cancel"}),e.jsx("button",{type:"submit",disabled:u,className:"px-4 py-1.5 rounded-lg bg-[#F65B66] text-white font-semibold hover:bg-[#E9505C]",children:u?"Creating…":"Create User"})]})]})]})})]})},Ic=[...Ne.map(n=>({id:n.id,label:Sn(n),color:n.color,modules:n.modules})),{id:"platform",label:"Platform services",color:"#9333EA",modules:Te},{id:"integrations",label:"Integrations",color:"#16834B",modules:He}],cn=n=>(an[n.id]??[]).map(t=>t.key),qc=[{id:"Institution",hint:"Entire organisation"},{id:"Department",hint:"Own department"},{id:"Assigned Records",hint:"Assigned classes / athletes"},{id:"Self",hint:"Own records only"}],$c=()=>{const{ROLES:n,ROLE_LAYOUTS:t,ROLES_SOURCE:s}=et(),[i,a]=f.useState(()=>n.map(P=>({...P,permissions:[...P.permissions]}))),[o,m]=f.useState("department-admin"),[p,g]=f.useState(""),[u,k]=f.useState(!1),[h,l]=f.useState({}),[y,v]=f.useState(null),x=i.find(P=>P.id===o)??i[0],F=f.useMemo(()=>new Set(x.permissions),[x]),E=t[x.id],A=P=>{v(P),setTimeout(()=>v(null),3e3)},b=P=>a(R=>R.map(w=>w.id===o?P(w):w)),_=P=>{b(R=>({...R,dataScope:P})),A(`Sample setting: "${P}" is shown for ${x.title} but is not stored or enforced`)},C=p.trim().toLowerCase(),L=Ic.map(P=>({...P,modules:P.modules.filter(R=>!(C&&!R.name.toLowerCase().includes(C)&&!R.id.includes(C)||u&&!cn(R).some(w=>F.has(w))))})).filter(P=>P.modules.length>0);return e.jsxs("div",{className:"space-y-6",children:[y&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs",children:[e.jsx(Z,{className:"w-4 h-4 text-[#126B3D]"}),e.jsx("span",{children:y})]}),e.jsx(ve,{title:"Roles & Permissions",subtitle:e.jsxs(e.Fragment,{children:["Roles from the academy profile plus the platform roles. Modules check permission keys"," ",e.jsx("code",{className:"text-[#6B21A8]",children:"<module>:<resource>:<action>"}),", granted to roles in each module's contracts/permissions.yaml."]})}),e.jsx(xe,{stats:[{label:"Roles",icon:be,value:String(i.length),note:`${i.filter(P=>!P.system).length} from the profile + org-admin, super-admin`},{label:"Assigned users",icon:sn,value:i.reduce((P,R)=>P+R.userCount,0).toLocaleString("en-IN"),note:"Across all roles"},{label:"Keys for this role",icon:Pe,value:String(x.permissions.length),note:x.title},{label:"Dashboard layouts",icon:Le,value:String(Object.keys(t).length),note:"platform/identity/config/dashboards"}]}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs",children:[e.jsxs("div",{className:"text-[11px] font-bold uppercase tracking-wider text-[#475569] mb-3 flex items-center gap-1.5",children:[e.jsx(be,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),e.jsx("span",{children:"How access is decided (platform/identity)"})]}),e.jsx("div",{className:"grid grid-cols-2 md:grid-cols-5 gap-2",children:[{step:"1. User",sub:"Email and password (platform/identity)"},{step:"2. Role",sub:"From the academy profile, or a platform role"},{step:"3. Permission keys",sub:"Modules check keys, never roles"},{step:"4. Organisation",sub:"Row-level security on organisation_id"},{step:"5. Entitlement",sub:"Module must be in profile and plan"}].map((P,R)=>e.jsxs("div",{className:"flex items-center justify-between p-2.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0]",children:[e.jsxs("div",{className:"min-w-0",children:[e.jsx("div",{className:"text-xs font-bold text-[#7E22CE]",children:P.step}),e.jsx("div",{className:"text-[10px] text-[#475569] truncate",children:P.sub})]}),R<4&&e.jsx(Fe,{className:"hidden md:block w-3.5 h-3.5 text-[#64748B] flex-shrink-0"})]},P.step))})]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-12 gap-6 items-start",children:[e.jsxs("div",{className:"lg:col-span-4 bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs space-y-3 lg:sticky lg:top-20",children:[e.jsxs("div",{className:"flex items-center justify-between pb-2 border-b border-[#E2E8F0]",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F]",children:["Roles (",i.length,")"]}),e.jsx("span",{className:"text-[11px] text-[#64748B] truncate",title:s,children:s.replace("platform/identity/config/","")})]}),e.jsx("div",{className:"space-y-1 max-h-[60vh] overflow-y-auto pr-1",children:i.map(P=>{const R=P.id===o;return e.jsxs("button",{onClick:()=>m(P.id),className:`w-full text-left px-3 py-2.5 rounded-lg transition-all border ${R?"bg-[#7E22CE26] border-[#9333EA] shadow-xs":"border-transparent hover:bg-[#F6F8FB]"}`,children:[e.jsxs("div",{className:"flex items-center justify-between gap-2",children:[e.jsx("span",{className:`text-xs font-bold truncate ${R?"text-[#7E22CE]":"text-[#12233F]"}`,children:P.title}),P.system&&e.jsx("span",{className:"text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded bg-[#F39A1926] text-[#8A4F00] flex-shrink-0",children:"system"})]}),e.jsxs("div",{className:"mt-1 flex items-center gap-2 text-[10px] text-[#475569]",children:[e.jsx("span",{className:"font-mono text-[#64748B]",children:P.id}),e.jsx("span",{children:"•"}),e.jsxs("span",{children:[P.userCount.toLocaleString("en-IN")," users"]}),e.jsx("span",{children:"•"}),e.jsxs("span",{children:[P.permissions.length," keys"]})]})]},P.id)})})]}),e.jsxs("div",{className:"lg:col-span-8 space-y-6",children:[e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-5 shadow-2xs space-y-4",children:[e.jsxs("div",{className:"flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-3 border-b border-[#E2E8F0]",children:[e.jsxs("div",{children:[e.jsxs("div",{className:"flex items-center gap-2 flex-wrap",children:[e.jsx("h2",{className:"text-lg font-bold text-[#12233F]",children:x.title}),e.jsx("span",{className:"text-xs font-mono px-2 py-0.5 rounded bg-[#F1F5F9] text-[#475569]",children:x.id})]}),e.jsx("p",{className:"text-xs text-[#475569] mt-1 max-w-2xl",children:x.description})]}),e.jsxs("span",{className:"text-xs font-medium px-2.5 py-1 rounded bg-[#16834B26] text-[#126B3D] self-start whitespace-nowrap",children:[x.userCount.toLocaleString("en-IN")," users"]})]}),e.jsxs("div",{children:[e.jsxs("div",{className:"flex items-center justify-between mb-2",children:[e.jsx("label",{className:"text-xs font-bold uppercase tracking-wider text-[#12233F]",children:"Data scope"}),e.jsx("span",{className:"text-[11px] text-[#475569]",children:"Sample setting, not in the repo yet; row-level security is per organisation"})]}),e.jsx("div",{className:"grid grid-cols-2 sm:grid-cols-4 gap-2",children:qc.map(({id:P,hint:R})=>{const w=x.dataScope===P;return e.jsxs("button",{onClick:()=>_(P),className:`p-2.5 rounded-lg border text-left transition-all ${w?"border-[#9333EA] bg-[#7E22CE26] text-[#7E22CE] font-bold shadow-2xs":"border-[#E2E8F0] hover:bg-[#F6F8FB] text-[#475569]"}`,children:[e.jsxs("div",{className:"text-xs flex items-center justify-between",children:[e.jsx("span",{children:P}),w&&e.jsx(We,{className:"w-3.5 h-3.5"})]}),e.jsx("span",{className:"text-[10px] font-normal block mt-0.5 text-[#475569]",children:R})]},P)})})]}),e.jsxs("div",{className:"pt-3 border-t border-[#E2E8F0]",children:[e.jsxs("div",{className:"flex items-center justify-between mb-2",children:[e.jsxs("label",{className:"text-xs font-bold uppercase tracking-wider text-[#12233F] flex items-center gap-1.5",children:[e.jsx(Le,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),"Dashboard layout"]}),E&&e.jsx(X,{to:`/dashboards?role=${x.id}`,className:"text-[11px] text-[#7E22CE] hover:underline",children:"Preview dashboard →"})]}),E?e.jsxs(e.Fragment,{children:[e.jsxs("p",{className:"text-[11px] text-[#64748B] mb-2 font-mono",children:["platform/identity/config/dashboards/",E.role,".yaml",E.extends&&e.jsxs("span",{className:"text-[#475569]",children:[" · extends ",E.extends]})]}),e.jsx("div",{className:"flex flex-wrap gap-1.5",children:qe(x.id).map(P=>e.jsx("span",{className:"text-[10px] font-mono px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155]",children:P},P))})]}):e.jsx("p",{className:"text-[11px] text-[#475569]",children:"No dashboard layout. System roles use the admin console."})]})]}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden",children:[e.jsxs("div",{className:"p-4 border-b border-[#E2E8F0] bg-[#F6F8FB] flex flex-col md:flex-row md:items-center justify-between gap-3",children:[e.jsxs("div",{children:[e.jsxs("h3",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5",children:[e.jsx(Pe,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),"Permission keys · ",x.title]}),e.jsx("p",{className:"text-[11px] text-[#475569]",children:"Each chip is a key a module defines in its contracts/permissions.yaml. Grants are made there, by role name."})]}),e.jsxs("div",{className:"flex items-center gap-2 flex-wrap",children:[e.jsxs("div",{className:"relative",children:[e.jsx(ye,{className:"w-3.5 h-3.5 text-[#64748B] absolute left-2.5 top-1/2 -translate-y-1/2"}),e.jsx("input",{value:p,onChange:P=>g(P.target.value),placeholder:"Filter modules",className:"pl-8 pr-3 py-1.5 w-40 rounded-lg bg-[#FFFFFF] border border-[#E2E8F0] text-xs text-[#12233F] placeholder:text-[#64748B] focus:outline-none focus:border-[#9333EA]"})]}),e.jsxs("label",{className:"inline-flex items-center gap-1.5 text-[11px] text-[#334155] cursor-pointer",children:[e.jsx("input",{type:"checkbox",checked:u,onChange:P=>k(P.target.checked),className:"accent-[#7E22CE]"}),"Granted only"]})]})]}),e.jsxs("div",{className:"overflow-x-auto",children:[e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F1F5F9] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-2.5 px-4 min-w-[220px]",children:"Module"}),e.jsx("th",{className:"py-2.5 px-3 uppercase tracking-wider text-[11px]",children:"Permission keys"})]})}),L.map(P=>{const R=h[P.id],w=P.modules.reduce((T,M)=>T+cn(M).filter(j=>F.has(j)).length,0);return e.jsxs("tbody",{className:"divide-y divide-[#F1F5F9]",children:[e.jsx("tr",{className:"bg-[#FFFFFF]",children:e.jsx("td",{colSpan:2,className:"py-2 px-4",children:e.jsxs("button",{onClick:()=>l(T=>({...T,[P.id]:!T[P.id]})),className:"flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-[#334155] w-full",children:[R?e.jsx(Xt,{className:"w-3.5 h-3.5"}):e.jsx(en,{className:"w-3.5 h-3.5"}),e.jsx("span",{className:"w-2 h-2 rounded-full",style:{background:P.color}}),e.jsx("span",{children:P.label}),e.jsxs("span",{className:"ml-auto font-medium normal-case tracking-normal text-[#64748B]",children:[w," granted"]})]})})}),!R&&P.modules.map(T=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors",children:[e.jsxs("td",{className:"py-2 px-4",children:[e.jsx(X,{to:`/modules/${T.id}`,className:"font-semibold text-[#12233F] hover:text-[#7E22CE]",children:T.name}),e.jsx("div",{className:"text-[10px] font-mono text-[#64748B]",children:T.id})]}),e.jsx("td",{className:"py-2 px-3",children:cn(T).length===0?e.jsx("span",{className:"text-[11px] text-[#64748B]",children:"None defined yet"}):e.jsx("div",{className:"flex flex-wrap gap-1.5",children:cn(T).map(M=>{const j=F.has(M);return e.jsxs("span",{className:`inline-flex items-center gap-1 px-2 py-1 rounded-md font-mono text-[10px] ${j?"bg-[#16834B26] text-[#126B3D] shadow-2xs":"bg-[#F1F5F9] text-[#64748B]"}`,title:`${M}: ${j?"granted":"not granted"} to ${x.id}`,children:[j?e.jsx(We,{className:"w-3.5 h-3.5 stroke-[2.5]"}):e.jsx(ie,{className:"w-3.5 h-3.5 stroke-[2]"}),M]},M)})})})]},T.id))]},P.id)})]}),L.length===0&&e.jsx("p",{className:"p-6 text-center text-xs text-[#475569]",children:"No modules match."})]}),e.jsxs("div",{className:"p-3 bg-[#F6F8FB] border-t border-[#E2E8F0] flex items-center justify-between text-[11px] text-[#475569]",children:[e.jsxs("span",{className:"flex items-center gap-1.5",children:[e.jsx("span",{className:"w-2.5 h-2.5 rounded bg-[#16834B26] border border-[#16834B]/30"}),e.jsx("span",{children:"Granted"}),e.jsx("span",{className:"w-2.5 h-2.5 rounded bg-[#F1F5F9] border border-[#CBD5E1] ml-2"}),e.jsx("span",{children:"Not granted"})]}),e.jsxs("span",{children:[x.permissions.length," keys granted"]})]})]})]})]})]})},r=(n,t,s,i,a)=>({label:n,value:t,note:s,delta:i,tone:a}),d=(n,t,s,i,a,o)=>({ref:n,type:t,title:s,description:i,urgency:a,time:o}),c=(n,t,s,i,a)=>({time:n,title:t,who:s,ref:i,status:a}),Js={"web-portal-cms":{action:"Publish Notice",kpis:[r("Page views (30 days)","1.24 L","Public website traffic","+9.4%"),r("Published pages","342","Across 18 sections","+12"),r("Pending approvals","7","Notices awaiting sign-off","2 urgent","alert"),r("Uptime","99.98%","Last 30 days","SLA met")],chart:{title:"Website Traffic",subtitle:"Monthly visitors, desktop vs mobile",series:["Desktop","Mobile"],base:21e3,split:.42},breakdown:{title:"Top Sections",subtitle:"Views in the last 30 days",items:[["Admissions 2026",48210],["Notices & Circulars",26480],["Sports Programmes",19340],["Results",15620],["Tenders",6310]]},actions:[d("CMS-118","Notice","Merit List 2 announcement","Draft by Admissions Cell, needs Registrar approval","Urgent","20 mins ago"),d("CMS-117","Page update","Hostel fee structure 2026–27","Finance revision pending publication","Pending","2 hours ago"),d("CMS-115","Tender","Synthetic track resurfacing tender","Legal vetting complete, ready to publish","Review","Yesterday")],activity:[c("10:12 AM",'Published "Inter-University Athletics Meet" notice',"Web Admin","CMS-116"),c("09:40 AM","Homepage banner rotated","Web Admin","CMS-BNR-22"),c("Yesterday","Broken link report generated","System","CMS-LNK-07","Warning")]},admissions:{action:"Create Admission",kpis:[r("Total applications","1,284","Undergraduate & Masters","+11.2%"),r("Confirmed","486","Tuition fee paid in full","37.8%"),r("Under review","86","Requires Dean review","urgent","alert"),r("Shortlisted","824","Counselling invitations issued","64.2%")],chart:{title:"Applications Received",subtitle:"Monthly, general vs sports quota",series:["General","Sports quota"],base:210,split:.18},breakdown:{title:"Admissions Funnel",subtitle:"Batch 2026 conversion",items:[["Applications",1284],["Shortlisted",824],["Counselling",612],["Confirmed",486]],footer:["Overall acceptance","37.8%"]},actions:[d("ADM-1024","Application","Harpreet Singh — B.Tech CSE (Sports Analytics)","National sports merit certificate unverified","Urgent","45 mins ago"),d("ADM-1027","Application","Navneet Sandhu — M.P.Ed","Sports quota trial result awaited","Pending","3 hours ago"),d("ADM-ML2","Merit list","Merit List 2 publication","Ready for Dean of Admissions sign-off","Review","Yesterday")],activity:[c("10:30 AM","Application ADM-1026 confirmed","Admissions Cell","ADM-1026"),c("09:55 AM","Counselling slot allotted to 42 candidates","Admissions Cell","CNS-0610"),c("Yesterday","Document mismatch flagged","DigiLocker sync","ADM-1028","Warning")]},"student-information":{action:"Add Student",kpis:[r("Enrolled students","3,842","Active academic records","+4.8%"),r("Student-athletes","428","Linked athlete profiles","+8.2%"),r("Profile updates pending","64","Awaiting verification","9 urgent","alert"),r("ID cards issued","3,611","This academic year","94%")],chart:{title:"Student Records Updated",subtitle:"Monthly, by staff vs self-service",series:["Staff","Self-service"],base:900,split:.55},breakdown:{title:"Students by School",subtitle:"Current enrolment",items:[["Sports Sciences",1210],["Physical Education",980],["Management",702],["Computer Science & AI",590],["Humanities",360]]},actions:[d("SIS-2210","Name change","Gurleen Kaur — name correction","Gazette notification attached","Pending","1 hour ago"),d("SIS-2207","Category update","Ravi Kumar — category to SC","Certificate needs verification","Urgent","3 hours ago"),d("SIS-2199","Status","Semester break request","Medical leave for 1 semester","Review","Yesterday")],activity:[c("10:05 AM","Bulk ID cards printed (batch 14)","SIS Office","IDC-B14"),c("09:20 AM","Guardian contact updated","Student (self)","SIS-2208"),c("Yesterday","Duplicate record merged","SIS Office","SIS-DUP-31")]},"enrolment-registration":{action:"Open Registration",kpis:[r("Registered this semester","3,605","Of 3,842 enrolled","93.8%"),r("Electives allotted","2,940","Seat allocation complete","+210"),r("Pending registrations","237","Fee or hold issues","action","alert"),r("Sections formed","148","Across 42 programmes","+6")],chart:{title:"Registrations",subtitle:"Monthly, core vs elective",series:["Core","Elective"],base:520,split:.4},breakdown:{title:"Registration Holds",subtitle:"Why students are blocked",items:[["Fee due",112],["Library dues",48],["Document pending",39],["Disciplinary",6]]},actions:[d("REG-HLD","Hold review","112 students blocked for fee dues","Finance confirmation needed to release","Urgent","30 mins ago"),d("REG-ELC","Elective","Sports Psychology elective oversubscribed","84 requests for 60 seats","Pending","2 hours ago"),d("REG-SEC","Section","New section for B.P.Ed Semester 3","Faculty assignment pending","Review","Yesterday")],activity:[c("10:18 AM","Late registration window opened","Registrar","REG-WIN-3"),c("09:44 AM","Elective lottery run for 6 courses","System","REG-LOT-12"),c("Yesterday","Registration sync to LMS","System","REG-SYNC","Success")]},"academic-management":{action:"Add Course",kpis:[r("Programmes","42","UG, PG and diploma","+3"),r("Active courses","386","This semester","+18"),r("Curriculum revisions","9","Awaiting Board of Studies","pending","alert"),r("Faculty assigned","96%","Course-faculty mapping","312 faculty")],chart:{title:"Teaching Load",subtitle:"Credit hours per month, theory vs practical",series:["Theory","Practical"],base:4200,split:.45},breakdown:{title:"Courses by School",subtitle:"Running this semester",items:[["Sports Sciences",118],["Physical Education",94],["Management",72],["Computer Science & AI",64],["Humanities",38]]},actions:[d("BOS-14","Curriculum","B.Sc Sports Science syllabus revision","Board of Studies meeting on 12 Oct","Pending","1 hour ago"),d("CRS-302","Faculty load","3 courses without faculty","Strength & Conditioning lab sections","Urgent","4 hours ago"),d("CRS-288","Credit change","Sports Nutrition credits 3 → 4","Academic Council approval needed","Review","Yesterday")],activity:[c("10:02 AM","Course outcome mapping updated","Dr. R. Kaur","CRS-214"),c("09:15 AM",'New elective "Esports Management" created',"Academic Office","CRS-391"),c("Yesterday","Faculty load report exported","HoD, Sports Sciences","RPT-FL-10")]},lms:{action:"Create Course Content",kpis:[r("Active learners","3,214","Logged in this week","+6.1%"),r("Courses online","348","With published content","90%"),r("Assignments to grade","412","Across all faculty","overdue 38","alert"),r("Avg. completion","78%","Module completion rate","+3.2%")],chart:{title:"Learning Activity",subtitle:"Monthly submissions, assignments vs quizzes",series:["Assignments","Quizzes"],base:6800,split:.45},breakdown:{title:"Engagement by Programme",subtitle:"Active learners this week",items:[["B.P.Ed",820],["B.Sc Sports Science",760],["BBA Sports Mgmt",610],["B.Tech CSE",540],["M.P.Ed",484]]},actions:[d("LMS-GR","Grading","38 assignments past grading deadline","Biomechanics and Exercise Physiology","Urgent","25 mins ago"),d("LMS-PLG","Plagiarism","5 submissions flagged above 40%","Research Methods — Section B","Review","2 hours ago"),d("LMS-VID","Content","Lecture video upload failed","Sports Psychology week 6","Pending","Yesterday")],activity:[c("10:20 AM",'Quiz "Anatomy Unit 3" published',"Dr. R. Kaur","LMS-Q-884"),c("09:48 AM","142 submissions received","System","LMS-AS-219"),c("Yesterday","Discussion forum moderated","Faculty","LMS-FRM-41")]},examinations:{action:"Schedule Exam",kpis:[r("Exams scheduled","214","Mid-semester, October","+12"),r("Hall tickets issued","3,540","Of 3,605 registered","98.2%"),r("Results pending","12","Awaiting moderation","urgent","alert"),r("Pass rate","91.4%","Last semester","+1.8%")],chart:{title:"Evaluations Completed",subtitle:"Monthly, internal vs external",series:["Internal","External"],base:5200,split:.35},breakdown:{title:"Result Processing",subtitle:"Current exam cycle",items:[["Answer sheets received",7210],["Evaluated",6480],["Moderated",5120],["Published",4380]],footer:["Cycle completion","60.7%"]},actions:[d("EXM-238","Results","B.P.Ed Semester 5 results","Submitted for moderation by Controller","Urgent","1 hour ago"),d("EXM-241","Re-evaluation","27 re-evaluation requests","Fee received, evaluator assignment pending","Pending","3 hours ago"),d("EXM-244","Clash","Timetable clash for 14 students","Elective exams on same slot","Review","Yesterday")],activity:[c("10:35 AM","Results submitted for verification","Dr. Vikram Malhotra","EXM-238"),c("09:10 AM","Hall tickets generated (batch 4)","Exam Cell","HT-B4"),c("Yesterday","Question paper vault accessed","Controller of Exams","QPV-118","Warning")]},"timetable-attendance":{action:"Generate Timetable",kpis:[r("Classes today","286","Across 42 programmes","+4"),r("Avg. attendance","86.4%","This week","+1.2%"),r("Below 75%","214","Students at debarment risk","alert","alert"),r("Attendance to mark","19","Sessions not yet marked","today","muted")],chart:{title:"Attendance Sessions",subtitle:"Monthly, lectures vs practicals",series:["Lectures","Practicals"],base:5600,split:.4},breakdown:{title:"Attendance by School",subtitle:"Average this month",unit:"%",items:[["Sports Sciences",91],["Physical Education",88],["Management",85],["Computer Science & AI",83],["Humanities",80]]},actions:[d("ATT-DBR","Debarment","214 students below 75%","Warning letters to be issued","Urgent","40 mins ago"),d("TT-ROOM","Room clash","Seminar Hall B double-booked","Thursday 11:00, two sections","Pending","2 hours ago"),d("ATT-COR","Correction","6 attendance correction requests","Athletes on tournament duty","Review","Yesterday")],activity:[c("10:40 AM","Attendance marked for 64 sessions","Faculty","ATT-0610"),c("09:12 AM","Trial session roster locked","Rajinder Kumar","ATT-9041"),c("Yesterday","Timetable v3 published","Academic Office","TT-V3")]},"athlete-performance":{action:"Add Athlete",kpis:[r("Active athletes","428","16 competitive disciplines","+8.2%"),r("Fitness tests this month","312","Benchmarks recorded","+46"),r("Below benchmark","37","Need intervention plan","review","alert"),r("National-level athletes","64","Representing state or country","+5")],chart:{title:"Fitness Assessments",subtitle:"Monthly, field vs lab tests",series:["Field","Lab"],base:260,split:.35},breakdown:{title:"Athletes by Discipline",subtitle:"Top disciplines",items:[["Athletics",96],["Wrestling",58],["Hockey",52],["Shooting",41],["Boxing",38]]},actions:[d("ATH-4091","Performance","Sprint squad 100m times regressed","5 athletes slower by 0.2s or more","Urgent","1 hour ago"),d("ATH-CLR","Clearance","12 fitness clearances pending","Needed before inter-university meet","Pending","3 hours ago"),d("ATH-PLN","Plan","Off-season plan for wrestling squad","Coach submitted, HoD review","Review","Yesterday")],activity:[c("10:04 AM","Athlete performance biometric record updated","Col. Gurmeet Dhillon","ATH-4091"),c("09:30 AM","VO2 max results imported","Sports Science Lab","LAB-0610"),c("Yesterday","Wearable sync failed for 3 athletes","Wearables adapter","WRB-ERR-9","Warning")]},"training-video-analysis":{action:"Upload Video",kpis:[r("Training sessions","1,146","Logged this month","+12%"),r("Videos uploaded","524","Match and training footage","+88"),r("Reviews pending","43","Awaiting coach annotation","pending","alert"),r("Storage used","2.8 TB","Of 5 TB quota","56%","muted")],chart:{title:"Training Sessions",subtitle:"Monthly, team vs individual",series:["Team","Individual"],base:980,split:.4},breakdown:{title:"Videos by Sport",subtitle:"Uploaded this month",items:[["Hockey",132],["Athletics",118],["Wrestling",96],["Boxing",74],["Football",61]]},actions:[d("VID-773","Review","Hockey semi-final footage","Tactical review requested by head coach","Pending","2 hours ago"),d("VID-770","Annotation","Javelin technique breakdown","8 clips awaiting biomechanics notes","Review","5 hours ago"),d("VID-STR","Storage","Quota 56% used","Archive season 2025 footage","Pending","Yesterday")],activity:[c("10:22 AM",'Session plan "Speed endurance" assigned',"Coach Rajinder Kumar","TRN-552"),c("09:35 AM","24 clips tagged","Video Analyst","VID-768"),c("Yesterday","Match video shared with athlete","Coach","VID-761")]},"sports-nutrition-health":{action:"New Diet Plan",kpis:[r("Athletes on diet plans","286","Personalised nutrition","+14"),r("Physio sessions","418","This month","+9.6%"),r("Active injuries","23","Under rehabilitation","4 severe","alert"),r("Return-to-play","17","Cleared this month","+5")],chart:{title:"Clinic Visits",subtitle:"Monthly, physio vs medical",series:["Physio","Medical"],base:380,split:.38},breakdown:{title:"Injuries by Type",subtitle:"Current season",items:[["Hamstring strain",9],["Ankle sprain",7],["Shoulder",4],["Knee ligament",2],["Other",1]]},actions:[d("MED-881","Injury","ACL suspected — wrestling athlete","MRI referral needs approval","Urgent","35 mins ago"),d("NUT-214","Plan review","12 diet plans due for review","Pre-competition phase","Pending","3 hours ago"),d("MED-874","Clearance","Return-to-play for 3 athletes","Physio sign-off complete","Review","Yesterday")],activity:[c("10:28 AM","Rehab session logged","Physiotherapist","PHY-2291"),c("09:50 AM","Body composition scans uploaded","Nutritionist","NUT-BCS-14"),c("Yesterday","Supplement stock below threshold","Clinic store","NUT-STK-3","Warning")]},"tournament-events":{action:"Create Tournament",kpis:[r("Upcoming events","14","Next 60 days","+3"),r("Medals this season","86","Gold 29 · Silver 31 · Bronze 26","+12"),r("Entries pending","9","Federation registrations","deadline","alert"),r("Teams travelling","6","This month","112 athletes","muted")],chart:{title:"Medals Won",subtitle:"Monthly, individual vs team events",series:["Individual","Team"],base:14,split:.3},breakdown:{title:"Medals by Sport",subtitle:"This season",items:[["Athletics",24],["Wrestling",18],["Shooting",15],["Boxing",13],["Hockey",6]]},actions:[d("TRN-AIU","Entry","AIU Athletics entries close Friday","9 athletes not yet registered","Urgent","1 hour ago"),d("TRN-TRV","Travel","Hockey team travel to Bhopal","Rail tickets and per-diem approval","Pending","4 hours ago"),d("TRN-OFF","Officials","Technical officials for home meet","6 officials to confirm","Review","Yesterday")],activity:[c("10:15 AM","Fixture list published","Sports Office","FIX-1006"),c("09:00 AM","Results uploaded: State Boxing","Event Manager","RES-0605"),c("Yesterday","Accreditation cards printed","Sports Office","ACC-221")]},"sports-facilities":{action:"Add Facility",kpis:[r("Facilities","38","Grounds, courts, pools, gyms","+2"),r("Utilisation","81%","Booked hours this week","+6%"),r("Out of service","3","Under repair","alert","alert"),r("Safety audits due","5","This month","scheduled","muted")],chart:{title:"Facility Hours Used",subtitle:"Monthly, training vs events",series:["Training","Events"],base:3600,split:.22},breakdown:{title:"Utilisation by Facility",subtitle:"Booked hours this week",items:[["Synthetic Track",96],["Hockey Turf",88],["Aquatic Centre",74],["Wrestling Hall",70],["Indoor Stadium",63]]},actions:[d("FAC-POOL","Repair","Aquatic centre filtration pump","Vendor quote ₹2.4 L awaiting approval","Urgent","50 mins ago"),d("FAC-AUD","Safety audit","Shooting range annual audit","Due by 15 Oct","Pending","3 hours ago"),d("FAC-LGT","Upgrade","LED floodlights for hockey turf","Proposal for budget review","Review","Yesterday")],activity:[c("10:05 AM","Track marked available after resurfacing","Facility Manager","FAC-TRK"),c("09:30 AM","Gym equipment inspection logged","Facility Staff","FAC-GYM-12"),c("Yesterday","Pool chlorine level alert","Sensor","FAC-POOL-S2","Warning")]},"facility-booking":{action:"New Booking",kpis:[r("Bookings today","64","Classrooms, halls, venues","+8"),r("This month","1,412","Confirmed bookings","+11%"),r("Awaiting approval","18","Requests in queue","5 urgent","alert"),r("Cancellations","3.2%","This month","-0.8%","muted")],chart:{title:"Bookings",subtitle:"Monthly, academic vs sports venues",series:["Academic","Sports"],base:1200,split:.45},breakdown:{title:"Bookings by Venue Type",subtitle:"This month",items:[["Classrooms",520],["Sports venues",446],["Seminar halls",214],["Labs",148],["Auditorium",84]]},actions:[d("BKG-3391","Approval","Auditorium for Alumni Meet","20 Oct, 600 guests","Urgent","30 mins ago"),d("BKG-3388","Conflict","Indoor stadium double-booked","Badminton trials vs convocation rehearsal","Pending","2 hours ago"),d("BKG-3380","Recurring","Semester booking for Yoga Hall","3 days a week, Physical Education","Review","Yesterday")],activity:[c("10:10 AM","12 bookings auto-approved","System","BKG-AUTO"),c("09:25 AM","Seminar Hall A booked","HoD, Management","BKG-3392"),c("Yesterday","No-show released 4 slots","System","BKG-NS-6")]},"inventory-equipment":{action:"Issue Equipment",kpis:[r("Items in stock","12,480","Across 9 stores","+320"),r("Issued this month","1,936","Equipment and consumables","+7%"),r("Below reorder level","5","Need purchase indent","reorder","alert"),r("Overdue returns","42","Not returned on time","follow up","muted")],chart:{title:"Stock Movement",subtitle:"Monthly, issues vs returns",series:["Issued","Returned"],base:1700,split:.45},breakdown:{title:"Stock by Category",subtitle:"Items on hand",items:[["Sports equipment",4820],["Lab consumables",3110],["Stationery",2240],["Medical supplies",1310],["IT accessories",1e3]]},actions:[d("INV-RO","Reorder","Hockey balls below reorder level","40 left, reorder level 120","Urgent","1 hour ago"),d("INV-OVD","Overdue","42 items overdue for return","Mostly athletics spikes and kits","Pending","3 hours ago"),d("INV-AUD","Stock audit","Annual stock verification","Central store, 14 Oct","Review","Yesterday")],activity:[c("10:00 AM","24 javelins issued to athletics squad","Store Keeper","ISS-6610"),c("09:20 AM","GRN recorded for lab consumables","Store Keeper","GRN-2281"),c("Yesterday","Low stock alert: first-aid kits","System","INV-LS-11","Warning")]},"asset-management":{action:"Register Asset",kpis:[r("Fixed assets","6,214","Tagged and registered","+86"),r("Asset value","₹184 Cr","Net book value","+2.1%"),r("Audit due","312","Physical verification pending","due","alert"),r("Disposals pending","27","Condemnation committee","review","muted")],chart:{title:"Assets Added",subtitle:"Monthly, equipment vs infrastructure",series:["Equipment","Infrastructure"],base:70,split:.25},breakdown:{title:"Value by Category",subtitle:"₹ crore, net book value",items:[["Buildings",112],["Sports infrastructure",38],["Lab equipment",17],["IT hardware",11],["Vehicles",6]]},actions:[d("AST-AUD","Verification","312 assets due for verification","Block C and Sports Complex","Urgent","2 hours ago"),d("AST-DSP","Disposal","27 assets for condemnation","Committee meeting on 18 Oct","Pending","5 hours ago"),d("AST-TRF","Transfer","Treadmills moved to new gym","Location update approval","Review","Yesterday")],activity:[c("10:25 AM","86 assets tagged with QR labels","Asset Officer","AST-TAG-9"),c("09:15 AM","Depreciation run for September","System","AST-DEP-09"),c("Yesterday","Missing asset reported","Facility Staff","AST-MIS-4","Warning")]},maintenance:{action:"Raise Work Order",kpis:[r("Open work orders","58","Across campus","-6"),r("Completed this month","214","Closed work orders","+12%"),r("Overdue","11","Past target date","escalate","alert"),r("Preventive tasks","92%","On schedule","+4%")],chart:{title:"Work Orders Closed",subtitle:"Monthly, corrective vs preventive",series:["Corrective","Preventive"],base:190,split:.4},breakdown:{title:"Open Orders by Trade",subtitle:"Current backlog",items:[["Electrical",19],["Plumbing",14],["Civil",11],["HVAC",8],["Carpentry",6]]},actions:[d("WO-7781","Electrical","Hostel B power fluctuation","Reported by 40 residents","Urgent","20 mins ago"),d("WO-7774","Plumbing","Aquatic centre shower leakage","Vendor visit scheduled","Pending","3 hours ago"),d("WO-7769","AMC","Lift AMC renewal","Quote from 2 vendors received","Review","Yesterday")],activity:[c("10:30 AM","Work order WO-7779 closed","Maintenance Team","WO-7779"),c("09:40 AM","Preventive check: DG sets","Electrical","PM-DG-10"),c("Yesterday","SLA breached on WO-7760","System","WO-7760","Warning")]},"fees-accounts":{action:"Generate Invoice",kpis:[r("Collected this term","₹8.42 Cr","Autumn 2026","+12.4%"),r("Collection rate","91%","Of billed fees","+3%"),r("Outstanding dues","₹74 L","312 students","follow up","alert"),r("Reconciled","₹1.28 Cr","SBIePay, this week","matched")],chart:{title:"Fee Collection",subtitle:"₹ lakh per month, online vs counter",series:["Online","Counter"],base:140,split:.15},breakdown:{title:"Collection by Fee Head",subtitle:"₹ lakh, this term",items:[["Tuition",512],["Hostel",168],["Examination",74],["Sports & activity",52],["Transport",36]]},actions:[d("PAY-20481","Payment","Vendor payment for athletic track","Awaiting financial concurrence","Pending","24 mins ago"),d("FEE-REF","Refund","14 refund requests","Withdrawn admissions","Review","3 hours ago"),d("FEE-REC","Reconciliation","₹3.2 L unmatched in SBIePay","Transaction IDs missing","Urgent","Yesterday")],activity:[c("10:42 AM","Payment request created","P. Singh, CA","PAY-20481"),c("09:30 AM","Daily SBIePay settlement imported","System","SET-0610"),c("Yesterday","Fee reminder SMS sent to 312 students","Notification service","NTF-FEE-6")]},"budget-grants":{action:"New Budget Head",kpis:[r("Annual budget","₹96 Cr","FY 2026–27","+8%"),r("Utilised","48%","₹46 Cr spent","on track"),r("Grant UCs due","4","Utilisation certificates","deadline","alert"),r("Active grants","19","Khelo India, UGC, state","+3")],chart:{title:"Expenditure",subtitle:"₹ lakh per month, revenue vs capital",series:["Revenue","Capital"],base:720,split:.35},breakdown:{title:"Spend by Head",subtitle:"₹ crore, year to date",items:[["Salaries",21],["Sports infrastructure",11],["Academic",6],["Hostels",5],["Administration",3]]},actions:[d("UC-KI-26","Utilisation","Khelo India grant UC due","Submit by 31 Oct","Urgent","1 hour ago"),d("BUD-RE","Re-appropriation","₹40 L from Admin to Sports","Finance Committee approval","Pending","4 hours ago"),d("GRT-UGC","Grant","UGC research grant installment","Release letter received","Review","Yesterday")],activity:[c("10:12 AM","Quarterly budget report generated","Finance Officer","RPT-BUD-Q2"),c("09:20 AM","Grant ledger updated","Accounts","GRT-LED-19"),c("Yesterday","Head overspend warning: Travel","System","BUD-WRN-4","Warning")]},procurement:{action:"Raise Indent",kpis:[r("Open indents","46","Department requests","+9"),r("POs issued","₹3.6 Cr","This quarter","+14%"),r("Tenders live","5","On GeM and e-tender","closing","alert"),r("Vendors","284","Empanelled","+12")],chart:{title:"Purchase Orders",subtitle:"Monthly count, GeM vs open tender",series:["GeM","Open tender"],base:60,split:.3},breakdown:{title:"Spend by Category",subtitle:"₹ lakh, this quarter",items:[["Sports equipment",148],["Lab equipment",92],["IT",64],["Furniture",38],["Services",18]]},actions:[d("TND-112","Tender","Synthetic track resurfacing","Technical evaluation due","Urgent","2 hours ago"),d("IND-889","Indent","Boxing rings ×2","Budget availability check","Pending","4 hours ago"),d("PO-4410","PO","Gym equipment PO","Ready for Registrar signature","Review","Yesterday")],activity:[c("10:08 AM","PO issued on GeM","Purchase Officer","PO-4412"),c("09:45 AM","Bid opened for tender TND-110","Purchase Committee","TND-110"),c("Yesterday","GeM API key regenerated","Dr. A. Sharma","SEC-KEY-819")]},"hr-payroll":{action:"Run Payroll",kpis:[r("Employees","612","Teaching and non-teaching","+8"),r("Payroll (Sept)","₹4.1 Cr","Processed on time","paid"),r("Leave requests","23","Awaiting approval","pending","alert"),r("Vacancies","34","Sanctioned posts open","recruiting","muted")],chart:{title:"Payroll Cost",subtitle:"₹ lakh per month, teaching vs non-teaching",series:["Teaching","Non-teaching"],base:405,split:.38},breakdown:{title:"Staff by Category",subtitle:"Current headcount",items:[["Faculty",312],["Coaches",42],["Administrative",138],["Technical",72],["Support",48]]},actions:[d("LV-2291","Leave","23 leave requests pending","7 earned leave, 16 casual","Pending","30 mins ago"),d("PAY-OCT","Payroll","October payroll draft","DA arrears to include","Review","3 hours ago"),d("REC-COACH","Recruitment","Interview panel for 4 coaches","Dates to confirm","Urgent","Yesterday")],activity:[c("10:20 AM","Joining recorded: Assistant Professor","HR Office","EMP-612"),c("09:05 AM","Salary slips emailed","System","PAY-SEP"),c("Yesterday","Biometric attendance sync delayed","System","HR-BIO-2","Warning")]},"e-office":{action:"Create File",kpis:[r("Files in movement","418","Across 26 sections","+31"),r("Closed this month","296","Decisions recorded","+9%"),r("Pending > 7 days","38","Delayed files","escalate","alert"),r("Avg. turnaround","3.4 days","Per file","-0.6 d")],chart:{title:"Files Processed",subtitle:"Monthly, created vs closed",series:["Created","Closed"],base:320,split:.47},breakdown:{title:"Pending by Section",subtitle:"Files awaiting action",items:[["Registrar",84],["Finance",72],["Academic",58],["Sports",46],["Estate",31]]},actions:[d("EF-5521","File","Convocation 2026 arrangements","With Registrar for 9 days","Urgent","1 hour ago"),d("EF-5514","Noting","MoU with State Sports Dept.","Legal opinion attached","Pending","4 hours ago"),d("EF-5509","Circular","Revised travel allowance rules","Draft for VC approval","Review","Yesterday")],activity:[c("10:15 AM","File EF-5518 forwarded to Finance","Section Officer","EF-5518"),c("09:30 AM","Digital signature applied","Registrar","EF-5502"),c("Yesterday","12 dak entries digitised","Dak Section","DAK-0605")]},hostel:{action:"Allot Room",kpis:[r("Residents","1,846","In 8 hostels","+42"),r("Occupancy","94%","Of 1,960 beds","+3%"),r("Complaints open","27","Maintenance and mess","urgent 6","alert"),r("Mess satisfaction","4.1 / 5","Monthly survey","+0.2")],chart:{title:"Hostel Complaints",subtitle:"Monthly, maintenance vs mess",series:["Maintenance","Mess"],base:70,split:.35},breakdown:{title:"Occupancy by Hostel",subtitle:"Residents",items:[["Milkha Singh Boys",420],["Mary Kom Girls",360],["Dhyan Chand Boys",340],["P.T. Usha Girls",310],["International",96]]},actions:[d("HST-B","Electrical","Hostel B power fluctuation","Work order WO-7781 raised","Urgent","20 mins ago"),d("HST-ALT","Allotment","18 room change requests","Mostly athletes moving to sports block","Pending","3 hours ago"),d("HST-MESS","Mess","Athlete diet menu revision","Nutritionist recommendations","Review","Yesterday")],activity:[c("10:00 AM","Visitor entries logged: 46","Hostel Warden","VIS-0610"),c("09:10 AM","Room 214 allotted","Hostel Office","HST-ALT-88"),c("Yesterday","Late entry recorded","Gate system","HST-GATE-12","Warning")]},transport:{action:"Add Route",kpis:[r("Bus passes","1,124","Students and staff","+38"),r("Routes","22","28 vehicles","+1"),r("Vehicles in service","25","3 under maintenance","check","alert"),r("On-time trips","93%","This month","+2%")],chart:{title:"Trips Operated",subtitle:"Monthly, campus routes vs event travel",series:["Routes","Events"],base:1300,split:.12},breakdown:{title:"Riders by Route",subtitle:"Daily average",items:[["Route 1",386],["Route 2",214],["Route 3",168],["Route 4",142],["Route 5",98]]},actions:[d("TRP-HKY","Event travel","Bus for hockey team to Ludhiana","Departure Saturday 6 AM","Urgent","1 hour ago"),d("VEH-12","Fitness","Vehicle fitness certificate due","PB-11-CK-4412","Pending","5 hours ago"),d("RTE-NEW","Route","New route request: Bahadurgarh","46 students interested","Review","Yesterday")],activity:[c("10:05 AM","GPS alert cleared on Route 7","Transport Office","GPS-7"),c("09:00 AM","38 passes issued","Transport Office","PASS-0610"),c("Yesterday","Route 3 delayed 25 mins","GPS","RTE-3-DLY","Warning")]},library:{action:"Issue Book",kpis:[r("Collection","48,210","Books, journals, e-resources","+620"),r("Loans active","2,364","Currently issued","+5%"),r("Overdue","186","Past due date","fines","alert"),r("E-resource sessions","9,840","This month","+18%")],chart:{title:"Circulation",subtitle:"Monthly, print vs digital",series:["Print","Digital"],base:2900,split:.5},breakdown:{title:"Loans by Subject",subtitle:"Active loans",items:[["Sports Science",742],["Physical Education",610],["Management",412],["Computer Science",356],["Humanities",244]]},actions:[d("LIB-OVD","Overdue","186 overdue loans","Send reminder and fine notices","Pending","40 mins ago"),d("LIB-ACQ","Acquisition","124 titles requested by faculty","Budget ₹4.6 L","Review","4 hours ago"),d("LIB-SUB","Subscription","SPORTDiscus renewal","Expires 31 Oct","Urgent","Yesterday")],activity:[c("10:18 AM","62 books returned","Circulation Desk","LIB-RET-0610"),c("09:35 AM","New arrivals catalogued","Librarian","LIB-CAT-44"),c("Yesterday","RFID gate alarm","Security gate","LIB-GATE-3","Warning")]},"placement-career":{action:"Add Drive",kpis:[r("Students placed","312","Batch 2026, so far","+18%"),r("Recruiters","64","Visited campus","+11"),r("Offers awaiting response","27","Expire this week","follow up","alert"),r("Median package","₹5.8 LPA","Batch 2026","+0.6")],chart:{title:"Offers Made",subtitle:"Monthly, on-campus vs off-campus",series:["On-campus","Off-campus"],base:48,split:.3},breakdown:{title:"Placements by Sector",subtitle:"Batch 2026",items:[["Sports management",98],["Fitness & wellness",76],["Education",64],["IT & analytics",52],["Government",22]]},actions:[d("PLC-DEC","Drive","Decathlon recruitment drive","Confirm venue and shortlist","Urgent","1 hour ago"),d("PLC-OFR","Offers","27 offers pending acceptance","Deadline Friday","Pending","3 hours ago"),d("PLC-INT","Internship","SAI internship nominations","15 seats, 48 applicants","Review","Yesterday")],activity:[c("10:22 AM","8 offers released","Placement Cell","PLC-OFR-41"),c("09:15 AM","Resume workshop scheduled","Career Services","PLC-WS-6"),c("Yesterday","Recruiter registered","Recruiter portal","PLC-REC-64")]},alumni:{action:"Create Event",kpis:[r("Alumni registered","8,640","In the directory","+214"),r("Donations (FY)","₹62 L","Scholarships and facilities","+22%"),r("Profiles to verify","96","New registrations","pending","alert"),r("Event RSVPs","412","Alumni Meet 2026","+120")],chart:{title:"Alumni Engagement",subtitle:"Monthly, event attendance vs mentoring",series:["Events","Mentoring"],base:260,split:.4},breakdown:{title:"Alumni by Sector",subtitle:"Where they work",items:[["Coaching",2140],["Teaching",1980],["Armed forces & police",1420],["Sports admin",1180],["Corporate",920]]},actions:[d("ALM-MEET","Event","Alumni Meet 2026 logistics","Auditorium booking BKG-3391","Urgent","30 mins ago"),d("ALM-VER","Verification","96 profiles to verify","Match with degree records","Pending","4 hours ago"),d("ALM-DON","Donation","₹5 L scholarship pledge","Receipt and 80G certificate","Review","Yesterday")],activity:[c("10:10 AM","Newsletter sent to 8,640 alumni","Alumni Office","ALM-NL-10"),c("09:25 AM","Donation received ₹50,000","Payment gateway","DON-2291"),c("Yesterday","Mentor matched with 12 students","Alumni Office","ALM-MNT-12")]},grievance:{action:"Register Grievance",kpis:[r("Open cases","14","SGRC, anti-ragging, POSH-ICC","-3"),r("Resolved this year","128","Within timeline","94%"),r("Escalated","2","To Proctorial Committee","urgent","alert"),r("Avg. resolution","9 days","Target 15 days","-2 d")],chart:{title:"Grievances Received",subtitle:"Monthly, academic vs non-academic",series:["Academic","Non-academic"],base:14,split:.45},breakdown:{title:"Open Cases by Committee",subtitle:"Current",items:[["SGRC",6],["Hostel",4],["Anti-ragging",2],["POSH-ICC",1],["Examination",1]]},actions:[d("GRV-301","Escalation","Hostel grievance escalated","Proctorial Committee hearing","Urgent","1 hour ago"),d("GRV-298","Hearing","SGRC hearing on evaluation","Schedule within 7 days","Pending","4 hours ago"),d("GRV-294","Closure","Anti-ragging case closure report","Committee sign-off","Review","Yesterday")],activity:[c("10:00 AM","Case GRV-296 resolved","SGRC","GRV-296"),c("09:20 AM","Anti-ragging affidavit drive","Dean Students","ARG-2026"),c("Yesterday","Case nearing deadline","System","GRV-292","Warning")]},rti:{action:"Log RTI Request",kpis:[r("Requests this year","64","Under RTI Act 2005","+9"),r("Disposed in time","96%","Within 30 days","+2%"),r("Nearing deadline","3","Due within 48 hours","urgent","alert"),r("First appeals","4","Pending with FAA","review","muted")],chart:{title:"RTI Requests",subtitle:"Monthly, received vs disposed",series:["Received","Disposed"],base:6,split:.48},breakdown:{title:"Requests by Topic",subtitle:"This year",items:[["Admissions",21],["Recruitment",14],["Finance",12],["Examinations",10],["Sports",7]]},actions:[d("RTI-2611","Deadline","Recruitment records request","Due in 36 hours","Urgent","10 mins ago"),d("RTI-2608","Transfer","Request on state sports policy","Transfer to Sports Department","Pending","3 hours ago"),d("APL-04","First appeal","Appeal on admission merit list","Hearing with FAA","Review","Yesterday")],activity:[c("10:05 AM","Reply dispatched for RTI-2604","PIO","RTI-2604"),c("09:40 AM","Information sought from Exam Cell","APIO","RTI-2609"),c("Yesterday","Quarterly RTI return filed","PIO","RTI-QR-2")]},"iqac-accreditation":{action:"Upload Evidence",kpis:[r("NAAC criteria","7","Self-study report","82% ready"),r("Evidence files","1,412","Uploaded to repository","+96"),r("Action items open","18","From IQAC meetings","due","alert"),r("Feedback collected","3,120","Students and stakeholders","+640")],chart:{title:"Evidence Uploaded",subtitle:"Monthly, documents vs data templates",series:["Documents","Templates"],base:180,split:.4},breakdown:{title:"SSR Readiness by Criterion",subtitle:"Share complete",unit:"%",items:[["Curricular aspects",92],["Teaching-learning",88],["Research",71],["Infrastructure",90],["Student support",84]]},actions:[d("IQAC-AI-18","Action item","Research publication data missing","Criterion 3, 4 departments","Urgent","2 hours ago"),d("IQAC-AQAR","AQAR","AQAR 2025–26 draft","Review by IQAC coordinator","Pending","5 hours ago"),d("IQAC-FB","Feedback","Employer feedback survey","Launch to 64 recruiters","Review","Yesterday")],activity:[c("10:30 AM","96 evidence files uploaded","Departments","IQAC-EV-96"),c("09:10 AM","IQAC meeting minutes published","IQAC Coordinator","IQAC-MOM-9"),c("Yesterday","Data template rejected","IQAC","IQAC-TPL-12","Warning")]},"regulatory-reports":{action:"Prepare Report",kpis:[r("Returns filed","22","UGC, AISHE, NIRF this year","+4"),r("On-time filing","95%","Statutory deadlines","+5%"),r("Due this month","3","AISHE, NIRF, state return","deadline","alert"),r("Data completeness","88%","Fields auto-filled from modules","+9%")],chart:{title:"Reports Filed",subtitle:"Monthly, central vs state",series:["Central","State"],base:4,split:.4},breakdown:{title:"Reports by Regulator",subtitle:"This year",items:[["UGC",8],["AISHE",4],["NIRF",3],["State Govt.",5],["NAAC",2]]},actions:[d("AISHE-26","Return","AISHE 2025–26 data upload","Due 20 Oct","Urgent","1 hour ago"),d("NIRF-27","Ranking","NIRF data capture","Faculty and research sections","Pending","4 hours ago"),d("UGC-SFS","Compliance","UGC self-financing course return","Registrar sign-off","Review","Yesterday")],activity:[c("10:10 AM","Student data exported for AISHE","MIS Cell","RPT-AISHE"),c("09:30 AM","Compliance calendar updated","Registrar Office","CAL-COMP"),c("Yesterday","Validation errors in NIRF draft","System","NIRF-VAL","Warning")]},helpdesk:{action:"New Ticket",kpis:[r("Open tickets","24","Hostel, Wi-Fi & LMS","-5"),r("Resolved this week","186","Closed tickets","+12%"),r("High priority","6","Need attention now","urgent","alert"),r("Avg. resolution","4.2 h","This week","-0.8 h")],chart:{title:"Tickets",subtitle:"Monthly, raised vs resolved",series:["Raised","Resolved"],base:820,split:.48},breakdown:{title:"Open Tickets by Category",subtitle:"Current queue",items:[["Wi-Fi & network",9],["Hostel",6],["LMS access",4],["Fee portal",3],["Email",2]]},actions:[d("TCK-8830","Network","Wi-Fi down in Sports Complex","Affecting 3 halls","Urgent","15 mins ago"),d("TCK-8826","LMS","Students cannot submit quiz","Exercise Physiology, Section A","Pending","1 hour ago"),d("TCK-8819","Access","Email account for new faculty","8 accounts to create","Review","Yesterday")],activity:[c("09:48 AM","Ticket closed: Campus Wi-Fi credentials reissued","Sunita Verma","TCK-8812"),c("09:20 AM","14 tickets auto-assigned","System","TCK-AUTO"),c("Yesterday","Ticket reopened by user","Student","TCK-8794","Warning")]},"sla-management":{action:"Define SLA",kpis:[r("SLA policies","18","By ticket category","+2"),r("Met this month","94%","Within target time","+3%"),r("Breaches","11","This month","review","alert"),r("At risk now","4","Close to breach","watch","muted")],chart:{title:"SLA Outcomes",subtitle:"Monthly, met vs breached",series:["Met","Breached"],base:780,split:.06},breakdown:{title:"Breaches by Team",subtitle:"This month",items:[["Network",4],["Maintenance",3],["Hostel",2],["Finance",1],["Academic",1]]},actions:[d("SLA-NET","Breach","Network team: 4 breaches","Root-cause review","Urgent","1 hour ago"),d("SLA-ESC","Escalation","Escalation matrix update","Add hostel wardens","Pending","4 hours ago"),d("SLA-NEW","Policy","SLA for sports equipment requests","Proposed 48-hour target","Review","Yesterday")],activity:[c("10:00 AM","SLA timer paused (awaiting user)","System","TCK-8826"),c("09:15 AM","Monthly SLA report generated","Support Lead","RPT-SLA-09"),c("Yesterday","SLA breached on WO-7760","System","WO-7760","Warning")]},"knowledge-base":{action:"Write Article",kpis:[r("Articles","214","Published","+9"),r("Views this month","12,480","Self-service reads","+21%"),r("Outdated articles","17","Need review","update","alert"),r("Ticket deflection","31%","Solved without a ticket","+4%")],chart:{title:"Article Views",subtitle:"Monthly, students vs staff",series:["Students","Staff"],base:10500,split:.3},breakdown:{title:"Top Articles",subtitle:"Views this month",items:[["Connect to campus Wi-Fi",2410],["Pay fees online",1980],["Reset LMS password",1640],["Book a sports facility",1120],["Apply for hostel",880]]},actions:[d("KB-REV","Review","17 articles need review","Older than 12 months","Pending","2 hours ago"),d("KB-NEW","Gap","No article for exam re-evaluation","22 tickets on this topic","Urgent","5 hours ago"),d("KB-TRN","Translation","Regional-language versions of top 10","Translator assigned","Review","Yesterday")],activity:[c("10:12 AM","Article updated: Fee portal guide","Support Staff","KB-114"),c("09:30 AM","Article published: Facility booking","Support Lead","KB-214"),c("Yesterday","Low rating on Wi-Fi article","Users","KB-021","Warning")]},"incident-management":{action:"Report Incident",kpis:[r("Open incidents","5","Under investigation","-2"),r("Resolved this month","23","Closed with RCA","+4"),r("Major incidents","1","Service-wide impact","active","alert"),r("Mean time to restore","1.8 h","This month","-0.5 h")],chart:{title:"Incidents",subtitle:"Monthly, minor vs major",series:["Minor","Major"],base:24,split:.12},breakdown:{title:"Incidents by Service",subtitle:"This quarter",items:[["Network",21],["Power",12],["LMS",8],["Fee portal",5],["Email",3]]},actions:[d("INC-114","Major","Sports Complex network outage","Fibre cut, vendor on site","Urgent","15 mins ago"),d("PRB-022","Problem","Recurring LMS slowness","RCA due this week","Pending","4 hours ago"),d("INC-110","Post-mortem","Fee portal downtime review","Report ready for sign-off","Review","Yesterday")],activity:[c("10:05 AM","Incident INC-114 declared major","Support Lead","INC-114"),c("09:20 AM","Problem record PRB-022 linked","Support Staff","PRB-022"),c("Yesterday","Unauthorized download attempt blocked","RBAC policy","HR-PAYROLL-CONFIDENTIAL","Failed")]},"amc-vendor-support":{action:"Add Contract",kpis:[r("Active AMCs","46","Equipment and services","+3"),r("Annual value","₹2.9 Cr","AMC spend","+6%"),r("Expiring in 30 days","5","Renewal needed","renew","alert"),r("Vendor SLA met","91%","Service visits on time","+2%")],chart:{title:"Service Visits",subtitle:"Monthly, scheduled vs breakdown calls",series:["Scheduled","Breakdown"],base:120,split:.3},breakdown:{title:"AMC Value by Category",subtitle:"₹ lakh per year",items:[["Sports equipment",96],["IT & network",82],["Lifts & HVAC",54],["Lab equipment",38],["Security systems",20]]},actions:[d("AMC-LIFT","Renewal","Lift AMC expires 30 Oct","Quotes from 2 vendors received","Urgent","1 hour ago"),d("AMC-GYM","Service","Gym equipment quarterly service","Vendor visit to confirm","Pending","5 hours ago"),d("AMC-PEN","Penalty","Penalty for missed visits","Network vendor, 3 visits","Review","Yesterday")],activity:[c("10:20 AM","Service report uploaded","Vendor portal","AMC-SR-221"),c("09:10 AM","Contract renewed: CCTV AMC","Purchase Officer","AMC-CCTV"),c("Yesterday","Vendor missed scheduled visit","System","AMC-MISS-3","Warning")]},portfolio:{action:"New Portfolio",kpis:[r("Active portfolios","1,126","Learners with a live portfolio","+14%"),r("Items added (30 days)","3,480","Artworks, showreels, designs, papers","+9.2%"),r("Awaiting review","64","Submitted to mentors","18 overdue","alert"),r("Published","812","Shared on public profile","72%","muted")],chart:{title:"Portfolio Items Added",subtitle:"Monthly, creative works vs research & teaching",series:["Creative works","Research & teaching"],base:290,split:.35},breakdown:{title:"Portfolio Types",subtitle:"Items by type",items:[["Artworks & designs",1240],["Showreels & media",860],["Repertoire",540],["Teaching portfolios",420],["Research portfolios",380]]},actions:[d("PRT-412","Review","Final-year design portfolio","Mentor review due before jury","Urgent","30 mins ago"),d("PRT-409","Showreel","Film showreel upload too large","Re-encode and resubmit requested","Pending","3 hours ago"),d("PRT-401","Publish","12 portfolios ready to publish","Consent forms received","Review","Yesterday")],activity:[c("10:20 AM","Showreel added to performing arts portfolio","Student","PRT-415"),c("09:05 AM","Mentor feedback posted on design portfolio","Faculty","PRT-412"),c("Yesterday","Portfolio published to public profile","Student","PRT-398")]},projects:{action:"New Project",kpis:[r("Active projects","214","Capstone, film, research, live business","+18"),r("Teams","186","Average 3.4 members","+11"),r("Milestones due (7 days)","42","Across all projects","9 at risk","alert"),r("Completed this term","58","Final review passed","+22%")],chart:{title:"Milestones Completed",subtitle:"Monthly, on time vs late",series:["On time","Late"],base:120,split:.18},breakdown:{title:"Projects by Type",subtitle:"Active this term",items:[["Capstone",72],["Research",54],["Live business",38],["Film",29],["Artwork",21]]},actions:[d("PRJ-221","Milestone","Capstone mid-term review","9 teams missing prototype demo","Urgent","1 hour ago"),d("PRJ-217","Team change","Member transfer request","Student asked to move between teams","Pending","4 hours ago"),d("PRJ-210","Final review","Live business pitch panel","Panel of 3 to be confirmed","Review","Yesterday")],activity:[c("10:05 AM",'Milestone "Prototype" marked complete',"Team Lead","PRJ-219"),c("09:30 AM","Supervisor feedback added","Faculty","PRJ-221"),c("Yesterday","New film project created","Student","PRJ-224")]},"selection-process":{action:"Schedule Round",kpis:[r("Open selections","12","Auditions, squads, jury, moot court","+3"),r("Applicants","846","Across open selections","+21%"),r("Rounds this week","9","Auditions and jury rounds","3 today","muted"),r("Selected","132","Final lists published","15.6%")],chart:{title:"Applicants per Month",subtitle:"Shortlisted vs not shortlisted",series:["Shortlisted","Not shortlisted"],base:140,split:.55},breakdown:{title:"Selection Funnel",subtitle:"Current cycle",items:[["Applications",846],["Shortlisted",384],["Auditions / jury rounds",241],["Team selection",168],["Supervisor allocation",132]],footer:["Selection rate","15.6%"]},actions:[d("SEL-118","Jury round","Theatre casting panel","Two jurors not yet confirmed","Urgent","45 mins ago"),d("SEL-115","Squad","Inter-university football squad","Coach shortlist awaits approval","Pending","2 hours ago"),d("SEL-111","Allocation","Research supervisor allocation","18 students without supervisor","Review","Yesterday")],activity:[c("10:15 AM","Audition slots published","Coordinator","SEL-120"),c("09:10 AM","Moot court team list finalised","Faculty","SEL-117"),c("Yesterday","Shortlist exported for jury","Coordinator","SEL-116")]},productions:{action:"New Production",kpis:[r("Upcoming events","18","Next 30 days","+5"),r("Registrations","2,340","Participants and audience","+26%"),r("Venues booked","11","Halls, studios, auditoria","2 pending","alert"),r("Completed this term","34","Performances, exhibitions, hackathons","+8")],chart:{title:"Event Attendance",subtitle:"Monthly, participants vs audience",series:["Participants","Audience"],base:900,split:.6},breakdown:{title:"Events by Type",subtitle:"This academic year",items:[["Performances",22],["Exhibitions",16],["Competitions",14],["Hackathons",9],["Screenings",8],["Conferences",6]]},actions:[d("PRD-061","Venue","Annual showcase main hall","Booking clash with convocation rehearsal","Urgent","1 hour ago"),d("PRD-058","Budget","Hackathon prize budget","Finance approval pending","Pending","5 hours ago"),d("PRD-055","Programme","Film screening schedule","Final running order to review","Review","Yesterday")],activity:[c("10:30 AM","Exhibition registrations opened","Coordinator","PRD-063"),c("09:20 AM","Recital programme published","Faculty","PRD-060"),c("Yesterday","Conference speakers confirmed","Coordinator","PRD-057")]},"field-training":{action:"New Placement",kpis:[r("Learners on placement","486","Clinical, teaching, farm, internships, court","+12%"),r("Host sites","74","Hospitals, schools, farms, firms, courts","+6"),r("Logbooks to verify","58","Supervisor sign-off pending","14 overdue","alert"),r("Completed hours","38,200","This term","+9.8%")],chart:{title:"Placement Hours Logged",subtitle:"Monthly, verified vs pending",series:["Verified","Pending"],base:6200,split:.22},breakdown:{title:"Placements by Type",subtitle:"Current term",items:[["Internships",162],["Clinical rotations",118],["Teaching practice",96],["Farm rotations",64],["Court visits",46]]},actions:[d("FLD-204","Logbook","Clinical rotation logbooks","14 entries past the 7-day window","Urgent","40 mins ago"),d("FLD-199","Host site","New internship partner","MoU awaiting signature","Pending","3 hours ago"),d("FLD-196","Evaluation","Teaching practice assessments","Mentor scores to review","Review","Yesterday")],activity:[c("10:00 AM","Placement assigned to host school","Coordinator","FLD-207"),c("08:50 AM","Logbook verified by supervisor","Faculty","FLD-203"),c("Yesterday","Farm rotation schedule published","Coordinator","FLD-201")]},"skill-progress":{action:"New Assessment",kpis:[r("Learners tracked","2,140","With at least one assessment","+16%"),r("Assessments (30 days)","5,860","Technique, fitness, practicum, competencies","+11%"),r("Improving","68%","Score up since last term","+4 pts"),r("Needs attention","146","Declining two assessments in a row","review","alert")],chart:{title:"Assessments Recorded",subtitle:"Monthly, improving vs needs attention",series:["Improving","Needs attention"],base:820,split:.2},breakdown:{title:"Assessments by Area",subtitle:"Last 30 days",items:[["Technique",1980],["Competencies",1460],["Fitness",1320],["Practicum",1100]]},actions:[d("SKL-330","Rubric","Competency rubric update","New level descriptors need approval","Pending","2 hours ago"),d("SKL-326","Follow-up","146 learners declining","Assign mentors for follow-up","Urgent","3 hours ago"),d("SKL-321","Review","End-of-term progress reports","Ready for faculty review","Review","Yesterday")],activity:[c("10:25 AM","Fitness test results imported","Coach","SKL-333"),c("09:15 AM","Practicum assessment recorded","Faculty","SKL-331"),c("Yesterday","Skill framework published","Coordinator","SKL-328")]},identity:{action:"Add User",kpis:[r("User accounts","4,826","Across all roles","+3.1%"),r("Roles in use","16","From the academy profile","muted","muted"),r("Sign-ins (7 days)","18,420","Email and password","+6.4%"),r("Failed sign-ins","212","Last 7 days","review","alert")],chart:{title:"Sign-ins",subtitle:"Monthly, successful vs failed",series:["Successful","Failed"],base:72e3,split:.03},breakdown:{title:"Users by Role",subtitle:"Top roles",items:[["Student",3414],["Athlete",428],["Faculty / Instructor",312],["Coach",42],["Finance Staff",8]]},actions:[d("IDN-090","Accounts","28 accounts never signed in","Invited more than 14 days ago","Review","2 hours ago"),d("IDN-087","Failed sign-ins","Repeated failures on one account","Check with the user","Urgent","3 hours ago"),d("IDN-084","Role change","HoD role requested for faculty","Organisation admin to confirm","Pending","Yesterday")],activity:[c("10:40 AM","User account created","Organisation Admin","IDN-093"),c("09:55 AM","Role assigned: Coach","Organisation Admin","IDN-092"),c("Yesterday","Account signed in for the first time","User","IDN-089")]},tenancy:{action:"View Organisation",kpis:[r("Organisations","38","Registered on the platform","+4"),r("Pending approval","3","Academic packages awaiting super admin","review","alert"),r("Active","31","Can sign in","81.6%"),r("Academy types in use","9","Of 15 profiles","muted","muted")],chart:{title:"Registrations",subtitle:"Monthly, approved vs pending",series:["Approved","Pending"],base:6,split:.25},breakdown:{title:"Organisations by Academy Type",subtitle:"All organisations",items:[["Sports College",11],["Engineering College",8],["Arts Academy",6],["Law College",5],["Medical College",4]]},actions:[d("TEN-031","Approval","Academic package awaiting approval","Registered and email verified","Urgent","1 hour ago"),d("TEN-028","Package change","Change of academy type requested","Super admin to approve","Pending","6 hours ago"),d("TEN-025","Override","Module outside plan requested","Review entitlement override","Review","Yesterday")],activity:[c("10:12 AM","tenancy.organisation.registered","System","TEN-033"),c("09:40 AM","tenancy.organisation.approved","Super Admin","TEN-030"),c("Yesterday","tenancy.entitlement.changed","Organisation Admin","TEN-027")]},billing:{action:"View Plans",kpis:[r("Subscriptions","38","One per organisation","+4"),r("On trial","9","Trial plan","3 ending soon","alert"),r("Paid plans","29","Standard and premium","76.3%"),r("Upgrades (30 days)","5","Trial to paid","+2")],chart:{title:"Subscriptions",subtitle:"Monthly, paid vs trial",series:["Paid","Trial"],base:30,split:.25},breakdown:{title:"Organisations by Plan",subtitle:"Current subscriptions",items:[["Standard",18],["Premium",11],["Trial",9]]},actions:[d("BIL-044","Trial","3 trials end this week","Reminders sent to organisation admins","Urgent","2 hours ago"),d("BIL-041","Upgrade","Upgrade to premium requested","Payment adapter not configured","Pending","5 hours ago"),d("BIL-038","Plan","Standard plan limits update","Review student limit","Review","Yesterday")],activity:[c("10:05 AM","billing.subscription.started","System","BIL-046"),c("09:22 AM","billing.subscription.upgraded","Organisation Admin","BIL-043"),c("Yesterday","billing.trial.expired","System","BIL-040","Warning")]},workflow:{action:"New Workflow",kpis:[r("Active workflows","24","Approval and state machines","+3"),r("Items in flight","186","Awaiting a step","+12"),r("Overdue steps","17","Past their SLA","escalate","alert"),r("Completed (30 days)","1,420","Approvals closed","+8.6%")],chart:{title:"Approvals Completed",subtitle:"Monthly, within SLA vs late",series:["Within SLA","Late"],base:1300,split:.08},breakdown:{title:"Pending by Workflow",subtitle:"Items awaiting action",items:[["Leave approval",48],["Purchase indent",36],["Fee waiver",29],["Result moderation",24],["File movement",19]]},actions:[d("WFL-512","Escalation","17 steps past SLA","Escalate to next approver","Urgent","20 mins ago"),d("WFL-509","Delegation","HoD on leave for 5 days","Delegate approvals","Pending","2 hours ago"),d("WFL-503","Design","New hostel allotment flow","Review state machine","Review","Yesterday")],activity:[c("10:18 AM","Leave request approved","Department Admin","WFL-515"),c("09:44 AM","Purchase indent moved to finance","System","WFL-514"),c("Yesterday","Workflow version published","Admin","WFL-506")]},audit:{action:"Export Audit Log",kpis:[r("Events (30 days)","48,200","State-changing actions","+5.2%"),r("Modules writing","6","Sending audit events","muted","muted"),r("Admin actions","312","Super admin and org admin","+18"),r("Impersonation sessions","4","All audited","review","alert")],chart:{title:"Audit Events",subtitle:"Monthly, user vs system",series:["User","System"],base:42e3,split:.3},breakdown:{title:"Events by Service",subtitle:"Last 30 days",items:[["identity",18400],["tenancy",9200],["billing",6100],["workflow",8300],["documents",6200]]},actions:[d("AUD-210","Impersonation","Super admin session reviewed","Confirm reason recorded","Review","1 hour ago"),d("AUD-206","Retention","Retention policy to set","Decide retention period per event type","Pending","1 day ago"),d("AUD-201","Export","Quarterly audit export","For governance review","Pending","2 days ago")],activity:[c("10:42 AM","tenancy.impersonation.started","Super Admin","AUD-212"),c("10:11 AM","identity.user.created","Organisation Admin","AUD-211"),c("Yesterday","tenancy.entitlement.changed","Organisation Admin","AUD-208")]},notification:{action:"New Template",kpis:[r("Messages (30 days)","62,400","Email, SMS, WhatsApp, push, in-app","+12%"),r("Delivered","98.4%","Across channels","+0.6 pts"),r("Templates","84","Active templates","+6"),r("Failed","1,010","Bounced or undelivered","review","alert")],chart:{title:"Messages Sent",subtitle:"Monthly, delivered vs failed",series:["Delivered","Failed"],base:58e3,split:.02},breakdown:{title:"Messages by Channel",subtitle:"Last 30 days",items:[["Email",24800],["In-app",16200],["SMS",11400],["WhatsApp",7600],["Push",2400]]},actions:[d("NTF-140","Bounces","Email bounces from one domain","412 bounces since Monday","Urgent","1 hour ago"),d("NTF-137","Template","Fee reminder template","Approval of new wording","Pending","4 hours ago"),d("NTF-133","Opt-outs","SMS opt-out requests","26 requests to process","Review","Yesterday")],activity:[c("10:30 AM","Trial expiry reminder sent","System","NTF-143"),c("09:15 AM","Exam schedule broadcast","Examination Staff","NTF-142"),c("Yesterday","Template updated: hostel notice","Admin","NTF-139")]},documents:{action:"Upload Document",kpis:[r("Documents","1.86 L","Stored across modules","+4.1%"),r("Storage used","612 GB","Of plan limit","61%","muted"),r("Uploads (30 days)","9,840","New files and versions","+7.3%"),r("Access requests","23","Awaiting owner approval","review","alert")],chart:{title:"Uploads",subtitle:"Monthly, new files vs new versions",series:["New files","New versions"],base:8600,split:.3},breakdown:{title:"Storage by Module",subtitle:"GB used",items:[["Admissions",182],["Training & video",164],["Student information",96],["E-Office",88],["LMS",82]]},actions:[d("DOC-301","Access","23 access requests","Owners to approve or deny","Pending","2 hours ago"),d("DOC-298","Storage","Video storage growing fast","Review retention for raw footage","Review","5 hours ago"),d("DOC-294","Scan","Unreadable scanned certificates","41 files to re-scan","Urgent","Yesterday")],activity:[c("10:22 AM","New version of fee circular","Finance Staff","DOC-304"),c("09:48 AM","Batch upload: hall tickets","Examination Staff","DOC-303"),c("Yesterday","Folder permissions changed","Admin","DOC-299")]},reporting:{action:"New Report",kpis:[r("Reports","146","MIS and dashboards","+9"),r("Runs (30 days)","4,320","Scheduled and on demand","+14%"),r("Scheduled","38","Delivered by email","muted","muted"),r("Failed runs","12","Last 30 days","review","alert")],chart:{title:"Report Runs",subtitle:"Monthly, scheduled vs on demand",series:["Scheduled","On demand"],base:3900,split:.45},breakdown:{title:"Most Used Reports",subtitle:"Runs in the last 30 days",items:[["Attendance by department",620],["Fee collection",540],["Results summary",410],["Admissions funnel",380],["Hostel occupancy",210]]},actions:[d("RPT-077","Failure","Nightly fee report failed","Source data late","Urgent","1 hour ago"),d("RPT-074","Request","New NAAC criterion report","Requested by IQAC","Pending","6 hours ago"),d("RPT-070","Schedule","Weekly management pack","Recipients to confirm","Review","Yesterday")],activity:[c("10:01 AM","Attendance report generated","Department Admin","RPT-080"),c("08:30 AM","Management pack emailed","System","RPT-079"),c("Yesterday","Report definition updated","Admin","RPT-072")]},search:{action:"Rebuild Index",kpis:[r("Searches (30 days)","84,600","Across modules","+18%"),r("Indexed records","6.2 L","Students, files, notices, more","+3.4%"),r("Zero-result searches","4.1%","No match found","-0.8 pts"),r("Index lag","42 s","Average time to searchable","muted","muted")],chart:{title:"Searches",subtitle:"Monthly, found vs no result",series:["Found","No result"],base:78e3,split:.04},breakdown:{title:"Searches by Area",subtitle:"Last 30 days",items:[["Students",31200],["Documents",18400],["Notices",14600],["Courses",11200],["Staff",9200]]},actions:[d("SRC-021","Synonyms","Top zero-result terms","Add synonyms for 14 terms","Review","2 hours ago"),d("SRC-019","Index","Library catalogue not indexed","Connect once library is enabled","Pending","1 day ago"),d("SRC-016","Lag","Index lag spike","Investigate during peak","Urgent","Yesterday")],activity:[c("10:10 AM","Notices index refreshed","System","SRC-024"),c("09:00 AM","Synonym list updated","Admin","SRC-022"),c("Yesterday","Full re-index completed","System","SRC-018")]},scheduler:{action:"New Job",kpis:[r("Scheduled jobs","64","Cron and one-off","+5"),r("Runs (24 hours)","1,920","Jobs executed","+2.1%"),r("Success rate","99.2%","Last 7 days","+0.3 pts"),r("Failed runs","15","Last 7 days","review","alert")],chart:{title:"Job Runs",subtitle:"Monthly, succeeded vs failed",series:["Succeeded","Failed"],base:56e3,split:.01},breakdown:{title:"Jobs by Type",subtitle:"Active jobs",items:[["Reminders",22],["Report delivery",14],["Data sync",12],["Clean-up",9],["Alerts",7]]},actions:[d("SCH-061","Failure","Trial expiry job failed twice","Check retry settings","Urgent","1 hour ago"),d("SCH-058","New job","Daily attendance alert","Approve schedule","Pending","4 hours ago"),d("SCH-055","Overlap","Two jobs at 02:00","Stagger to reduce load","Review","Yesterday")],activity:[c("10:00 AM","Fee reminder job completed","System","SCH-064"),c("06:00 AM","Nightly clean-up completed","System","SCH-063"),c("Yesterday","Trial expiry job retried","System","SCH-060","Warning")]},"event-bus":{action:"View Contracts",kpis:[r("Events (24 hours)","1.12 L","Published between modules","+6.8%"),r("Event types","29","Defined in contracts/events.yaml","+6"),r("Consumers","11","Subscribed modules","muted","muted"),r("Dead letters","18","Failed after retries","review","alert")],chart:{title:"Events Published",subtitle:"Monthly, delivered vs retried",series:["Delivered","Retried"],base:32e5,split:.02},breakdown:{title:"Events by Publisher",subtitle:"Last 24 hours",items:[["identity",38200],["tenancy",24600],["billing",18300],["workflow",17900],["notification",13e3]]},actions:[d("EVB-033","Dead letters","18 events failed delivery","Inspect and replay","Urgent","45 mins ago"),d("EVB-030","Contract","New event type proposed","training-video-analysis.video.tagged","Review","3 hours ago"),d("EVB-027","Consumer","Slow consumer lag","Reporting consumer behind by 4 min","Pending","Yesterday")],activity:[c("10:35 AM","tenancy.entitlement.changed delivered","System","EVB-036"),c("10:02 AM","billing.subscription.started delivered","System","EVB-035"),c("Yesterday","Dead-letter replay completed","Admin","EVB-029")]},"integration-hub":{action:"Add Adapter",kpis:[r("Adapters","8","Registered integrations","muted","muted"),r("Exchanges (30 days)","24,600","XML, JSON and CSV files","+9.5%"),r("Webhooks","14","Inbound endpoints","+2"),r("Failed exchanges","37","Retry queue","review","alert")],chart:{title:"Data Exchanges",subtitle:"Monthly, succeeded vs retried",series:["Succeeded","Retried"],base:22e3,split:.05},breakdown:{title:"Exchanges by Adapter",subtitle:"Last 30 days",items:[["Email / SMS / WhatsApp",11200],["SBIePay",5400],["DigiLocker",3100],["Government portals",2600],["Video conferencing",2300]]},actions:[d("INT-052","Retry","37 exchanges in retry queue","Government portal timeouts","Urgent","1 hour ago"),d("INT-049","Credentials","API key rotation due","Payment gateway key expires soon","Pending","5 hours ago"),d("INT-046","Mapping","AISHE CSV mapping change","Review new column layout","Review","Yesterday")],activity:[c("10:20 AM","DigiLocker batch exchanged","System","INT-055"),c("09:30 AM","Webhook endpoint added","Admin","INT-054"),c("Yesterday","Retry batch processed","System","INT-050","Warning")]},"api-gateway":{action:"View Routes",kpis:[r("Requests (24 hours)","3.4 L","Through the gateway","+7.2%"),r("Routes","126","Across modules","+14"),r("p95 latency","186 ms","Last 24 hours","-12 ms"),r("Rejected requests","2,140","Outside entitlement or rate limit","review","alert")],chart:{title:"Requests",subtitle:"Monthly, allowed vs rejected",series:["Allowed","Rejected"],base:96e5,split:.01},breakdown:{title:"Requests by Service",subtitle:"Last 24 hours",items:[["identity",112e3],["tenancy",64e3],["admissions",58e3],["lms",52e3],["billing",54e3]]},actions:[d("GTW-071","Rate limit","One client hitting limits","Raise limit or contact organisation","Review","1 hour ago"),d("GTW-068","Route","New module routes to publish","Skill progress API","Pending","6 hours ago"),d("GTW-064","Latency","p95 spike at 09:00","Investigate peak load","Urgent","Yesterday")],activity:[c("10:45 AM","Route table reloaded","System","GTW-074"),c("09:05 AM","Rate limit raised for one organisation","Admin","GTW-073"),c("Yesterday","Entitlement rejections reviewed","Admin","GTW-066")]},"payment-sbiepay":{action:"Test Connection",kpis:[r("Transactions (30 days)","8,420","Initiated through SBIePay","+11%"),r("Collected","₹4.86 Cr","Successful payments","+9.6%"),r("Success rate","97.8%","Paid on first attempt","+0.4 pts"),r("To reconcile","36","Callback without settlement","review","alert")],chart:{title:"Payments",subtitle:"Monthly, successful vs failed",series:["Successful","Failed"],base:7800,split:.03},breakdown:{title:"Payments by Purpose",subtitle:"Last 30 days",items:[["Tuition fees",5120],["Hostel fees",1640],["Application fees",980],["Event registrations",480],["Fines",200]]},actions:[d("PAY-301","Reconcile","36 payments not settled","Match against settlement file","Urgent","1 hour ago"),d("PAY-298","Refund","Duplicate payment refund","Finance approval needed","Pending","4 hours ago"),d("PAY-294","Config","Merchant key rotation","Due this month","Review","Yesterday")],activity:[c("10:28 AM","Payment callback received","SBIePay","PAY-305"),c("06:00 AM","Settlement file reconciled","System","PAY-304"),c("Yesterday","Payment failed: bank timeout","SBIePay","PAY-300","Failed")]},digilocker:{action:"Test Connection",kpis:[r("Certificates issued","3,260","Pushed to DigiLocker","+18%"),r("Verifications","1,140","Documents fetched from students","+9.2%"),r("Pending issue","84","Awaiting signature","review","alert"),r("Success rate","99.1%","Issue and fetch","+0.2 pts")],chart:{title:"DigiLocker Activity",subtitle:"Monthly, issued vs verified",series:["Issued","Verified"],base:820,split:.35},breakdown:{title:"Documents by Type",subtitle:"This year",items:[["Degree certificates",1420],["Marksheets",1180],["Migration certificates",360],["Transfer certificates",300]]},actions:[d("DGL-041","Signature","84 certificates to sign","Controller of Examinations","Urgent","2 hours ago"),d("DGL-038","Mismatch","Name mismatch on 6 records","Correct before issue","Pending","5 hours ago"),d("DGL-035","Batch","Convocation batch ready","Review before push","Review","Yesterday")],activity:[c("10:14 AM","Marksheets pushed to DigiLocker","System","DGL-044"),c("09:20 AM","Applicant document fetched","Admissions","DGL-043"),c("Yesterday","Issue failed: invalid Aadhaar link","DigiLocker","DGL-040","Failed")]},nad:{action:"Test Connection",kpis:[r("Records lodged","2,940","Academic awards on NAD","+14%"),r("Pending lodging","128","Results not yet sent","review","alert"),r("Verification requests","410","From employers and institutions","+22%"),r("Success rate","98.6%","Lodge and verify","+0.5 pts")],chart:{title:"NAD Records",subtitle:"Monthly, lodged vs verified",series:["Lodged","Verified"],base:620,split:.3},breakdown:{title:"Records by Programme",subtitle:"This year",items:[["Undergraduate",1680],["Postgraduate",820],["Diploma",290],["Doctoral",150]]},actions:[d("NAD-022","Lodging","128 results pending","Semester results to lodge","Urgent","3 hours ago"),d("NAD-019","Correction","Record correction request","Grade change approved","Pending","1 day ago"),d("NAD-016","Mapping","Programme codes update","Match new NAD codes","Review","2 days ago")],activity:[c("10:00 AM","Results batch lodged","System","NAD-025"),c("Yesterday","Employer verification answered","NAD","NAD-024"),c("Yesterday","Lodging failed: missing roll number","NAD","NAD-021","Failed")]},"government-portals":{action:"Test Connection",kpis:[r("Submissions (this year)","24","UGC, AISHE, NAAC and others","+5"),r("Due in 30 days","4","Statutory returns","1 overdue","alert"),r("Accepted","19","Acknowledged by portal","79%"),r("Data checks failed","7","Before submission","review","alert")],chart:{title:"Portal Submissions",subtitle:"Monthly, accepted vs returned",series:["Accepted","Returned"],base:4,split:.2},breakdown:{title:"Submissions by Portal",subtitle:"This year",items:[["AISHE",6],["UGC",7],["NAAC",4],["NIRF",3],["State government",4]]},actions:[d("GOV-017","Overdue","AISHE return overdue","Faculty data incomplete","Urgent","2 hours ago"),d("GOV-014","Data check","7 validation errors","Fix before UGC upload","Pending","1 day ago"),d("GOV-011","NIRF","NIRF data capture","Review draft figures","Review","2 days ago")],activity:[c("09:40 AM","UGC return acknowledged","UGC portal","GOV-020"),c("Yesterday","NAAC data uploaded","IQAC","GOV-019"),c("Yesterday","AISHE upload rejected","AISHE portal","GOV-016","Failed")]},"messaging-providers":{action:"Test Connection",kpis:[r("Messages (30 days)","45,200","Email, SMS and WhatsApp","+12%"),r("Delivery rate","98.1%","Across providers","+0.4 pts"),r("Providers","3","Email, SMS, WhatsApp","muted","muted"),r("Provider errors","860","Last 30 days","review","alert")],chart:{title:"Messages Sent",subtitle:"Monthly, delivered vs failed",series:["Delivered","Failed"],base:42e3,split:.02},breakdown:{title:"Messages by Provider",subtitle:"Last 30 days",items:[["Email",24800],["SMS",11400],["WhatsApp",9e3]]},actions:[d("MSG-029","Errors","SMS provider timeouts","312 retries since morning","Urgent","1 hour ago"),d("MSG-026","Template","WhatsApp template approval","Waiting for provider approval","Pending","6 hours ago"),d("MSG-023","Domain","Email sender domain check","Review sending domain settings","Review","Yesterday")],activity:[c("10:32 AM","Batch sent: fee reminders","System","MSG-032"),c("09:12 AM","Provider failover to backup SMS","System","MSG-031","Warning"),c("Yesterday","WhatsApp template approved","Provider","MSG-028")]},"video-conferencing":{action:"Test Connection",kpis:[r("Meetings (30 days)","1,860","Online classes and meetings","+15%"),r("Hours hosted","3,420","Total meeting time","+12%"),r("Recordings","1,140","Saved to documents","+9%"),r("Join failures","46","Last 30 days","review","alert")],chart:{title:"Meetings Hosted",subtitle:"Monthly, classes vs meetings",series:["Classes","Meetings"],base:1700,split:.3},breakdown:{title:"Meetings by Platform",subtitle:"Last 30 days",items:[["Zoom",820],["Microsoft Teams",640],["Webex",400]]},actions:[d("VC-038","Licences","Licence limit near","92% of hosts in use","Urgent","2 hours ago"),d("VC-035","Recording","Recordings not synced","14 recordings pending upload","Pending","5 hours ago"),d("VC-031","Settings","Waiting room policy","Review for exams","Review","Yesterday")],activity:[c("10:00 AM","Class meeting created from timetable","System","VC-041"),c("09:30 AM","Recording saved","System","VC-040"),c("Yesterday","Join failed: expired link","Zoom","VC-037","Failed")]},wearables:{action:"Test Connection",kpis:[r("Connected devices","412","Athlete wearables","+38"),r("Readings (7 days)","1.8 L","Heart rate, load, sleep","+11%"),r("Athletes covered","96%","Of active athletes","+4 pts"),r("High-load alerts","23","Last 7 days","review","alert")],chart:{title:"Readings Received",subtitle:"Monthly, training vs recovery",series:["Training","Recovery"],base:7e5,split:.4},breakdown:{title:"Devices by Sport",subtitle:"Connected devices",items:[["Athletics",128],["Football",96],["Hockey",74],["Wrestling",62],["Swimming",52]]},actions:[d("WRB-027","Alert","23 high-load alerts","Coaches to review training load","Urgent","40 mins ago"),d("WRB-024","Sync","18 devices not synced","No data for 3 days","Pending","4 hours ago"),d("WRB-021","Consent","Data consent renewals","Athletes to re-confirm","Review","Yesterday")],activity:[c("10:20 AM","Overnight recovery data synced","System","WRB-030"),c("08:45 AM","High-load alert raised","System","WRB-029","Warning"),c("Yesterday","New devices paired","Coach","WRB-026")]},"external-university-portals":{action:"Test Connection",kpis:[r("Partner institutions","14","Connected portals","+2"),r("Exchanges (30 days)","1,260","Credits, transcripts, enrolments","+16%"),r("Credit transfers","184","Processed this term","+28"),r("Failed exchanges","9","Last 30 days","review","alert")],chart:{title:"Data Exchanges",subtitle:"Monthly, sent vs received",series:["Sent","Received"],base:1100,split:.45},breakdown:{title:"Exchanges by Type",subtitle:"Last 30 days",items:[["Transcripts",520],["Credit transfers",340],["Enrolment checks",260],["Exchange students",140]]},actions:[d("EXT-015","Credit","12 credit transfers to approve","From partner university","Pending","3 hours ago"),d("EXT-012","Failure","Transcript exchange failed","Partner portal unavailable","Urgent","5 hours ago"),d("EXT-009","Partner","New partner onboarding","Agree data format","Review","Yesterday")],activity:[c("10:05 AM","Transcripts sent to partner","System","EXT-018"),c("Yesterday","Credit transfer received","Partner portal","EXT-017"),c("Yesterday","Exchange failed: timeout","Partner portal","EXT-014","Failed")]}};function Vc(n){const t=n.kind==="integration";return{action:t?"Test Connection":"Open Settings",kpis:t?[r("Requests (30 days)","18,420","Calls through the adapter","+7%"),r("Success rate","99.2%","Responses without error","healthy"),r("Failed calls","146","Retried by integration hub","review","alert"),r("Avg. latency","420 ms","Round trip","-30 ms")]:[r("Requests (30 days)","2.4 L","From all modules","+11%"),r("Availability","99.97%","Last 30 days","SLA met"),r("Errors","38","Logged this month","review","alert"),r("Modules using it","36","Through packages/sdk","all")],chart:{title:"Requests",subtitle:"Monthly, successful vs retried",series:["Successful","Retried"],base:t?3e3:4e4,split:.04},breakdown:{title:"Top Callers",subtitle:"Requests this month",items:[["Admissions",4200],["Fees & Accounts",3600],["Examinations",2900],["Student Information",2100],["Helpdesk",1300]]},actions:[d(`${n.id.toUpperCase().slice(0,6)}-01`,"Configuration",`Review ${n.name} configuration`,"Keys listed in config/env.example","Review","2 hours ago"),d(`${n.id.toUpperCase().slice(0,6)}-02`,"Errors","Recurring errors this week","Inspect logs in monitoring","Pending","Yesterday")],activity:[c("10:00 AM","Health check passed","Monitoring",`${n.id}-HC`),c("Yesterday","Configuration reloaded","System",`${n.id}-CFG`)]}}const Hc=["Apr","May","Jun","Jul","Aug","Sep"];function Xs(n,t,s=0){let i=[...n].reduce((o,m)=>o*31+m.charCodeAt(0)>>>0,7);const a=()=>(i=i*1664525+1013904223>>>0,i/2**32);return Hc.map((o,m)=>{const p=.82+m*.05,g=Math.max(1,Math.round(t*p*(.85+a()*.3))),u=Math.round(g*s);return{month:o,a:g-u,b:u}})}const De=Js.admissions,Uc=()=>{const[n,t]=f.useState(Ed),[s,i]=f.useState(!1);f.useEffect(()=>{const w=new Image;w.onload=()=>i(!0),w.src=B("/admissions.jpg")},[]);const[a,o]=f.useState(""),[m,p]=f.useState("All"),[g,u]=f.useState("All"),[k,h]=f.useState("All"),[l,y]=f.useState(null),[v,x]=f.useState(!1),[F,E]=f.useState(null),A=w=>{E(w),setTimeout(()=>E(null),3500)},b=w=>{y(w),x(!0)},_=()=>{x(!1),y(null)},C=w=>{t(T=>T.map(M=>{if(M.id===w){const j={...M,status:"Confirmed",timeline:M.timeline.map(O=>O.step==="Document Verification"?{...O,status:"completed",note:"Statutory verification signed off by Admissions Committee"}:O.step==="Confirmation & Registration"?{...O,status:"completed",timestamp:"Just now",note:"Marked confirmed (sample)"}:O)};return(l==null?void 0:l.id)===w&&y(j),j}return M})),A(`Sample only: ${w} marked Confirmed on this page. No letter is sent; the admissions module is not built yet.`)},L=w=>{t(T=>T.map(M=>{if(M.id===w){const j={...M,status:"Under Review",timeline:M.timeline.map(O=>O.step==="Document Verification"?{...O,status:"in-progress",note:"Changes requested (sample)"}:O)};return(l==null?void 0:l.id)===w&&y(j),j}return M})),A(`Sample only: ${w} sent back to review on this page. No message is sent to the candidate.`)},P=w=>{if(!l)return;const T=l.documents.map(j=>j.id===w?{...j,verified:!j.verified}:j),M={...l,documents:T};y(M),t(j=>j.map(O=>O.id===M.id?M:O))},R=n.filter(w=>{const T=w.applicant.toLowerCase().includes(a.toLowerCase())||w.id.toLowerCase().includes(a.toLowerCase())||w.email.toLowerCase().includes(a.toLowerCase()),M=m==="All"||w.status===m,j=g==="All"||w.programme.includes(g),O=k==="All"||w.category===k;return T&&M&&j&&O});return e.jsxs(Ys,{theme:Gs("student-lifecycle"),className:"space-y-6",children:[F&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs",children:[e.jsx(Z,{className:"w-4 h-4 text-[#126B3D]"}),e.jsx("span",{children:F})]}),e.jsx(ve,{title:"Admissions",art:s?e.jsx(nt,{src:B("/admissions.jpg"),position:"70% 45%",tone:"violet"}):void 0,subtitle:"Application and verification workflow · Academic Year 2026–27",actions:e.jsxs("button",{onClick:()=>A("Export needs the admissions module, which is not built yet"),className:ae,children:[e.jsx(zn,{className:"w-3.5 h-3.5 text-[#475569]"}),"Export Roster"]})}),e.jsx(xe,{stats:[{label:"Total applications",icon:Ye,value:"1,284",note:"Undergraduate & Masters"},{label:"Confirmed",icon:Z,value:"486",delta:"37.8%",note:"Sample figure"},{label:"Under review",icon:nn,value:"86",delta:"Dean review",deltaTone:"alert",note:"Requires Dean review"},{label:"Shortlisted",icon:tn,value:"824",delta:"64.2%",deltaTone:"muted",note:"Counselling invitations issued"}]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsx(at,{className:"lg:col-span-2",title:De.chart.title,subtitle:De.chart.subtitle,data:Xs("admissions",De.chart.base,De.chart.split),xKey:"month",series:[{key:"a",name:De.chart.series[0]},{key:"b",name:De.chart.series[1]}],tooltipLabel:w=>`${w} 2026`}),e.jsx(it,{title:"Admissions Funnel",subtitle:"Batch 2026 conversion",relativeToFirst:!0,items:ks.map((w,T)=>({label:w.stage,count:w.count,color:ws[T]})),footer:{label:"Overall acceptance",value:"37.8%"}})]}),e.jsx("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs",children:e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3",children:[e.jsxs("div",{className:"relative",children:[e.jsx(ye,{className:"w-4 h-4 text-[#475569] absolute left-3 top-2.5"}),e.jsx("input",{type:"text",placeholder:"Search by candidate name or ID...",value:a,onChange:w=>o(w.target.value),className:"w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"})]}),e.jsx("div",{children:e.jsxs("select",{value:m,onChange:w=>p(w.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Statuses"}),e.jsx("option",{value:"Under Review",children:"Under Review"}),e.jsx("option",{value:"Shortlisted",children:"Shortlisted"}),e.jsx("option",{value:"Confirmed",children:"Confirmed"})]})}),e.jsx("div",{children:e.jsxs("select",{value:g,onChange:w=>u(w.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Programmes"}),e.jsx("option",{value:"B.Tech",children:"B.Tech CSE (Sports Analytics)"}),e.jsx("option",{value:"B.Sc",children:"B.Sc Sports Science & Biomechanics"}),e.jsx("option",{value:"BBA",children:"BBA Sports Management"}),e.jsx("option",{value:"M.P.Ed",children:"M.P.Ed Physical Education"})]})}),e.jsx("div",{children:e.jsxs("select",{value:k,onChange:w=>h(w.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Categories"}),e.jsx("option",{value:"General",children:"General"}),e.jsx("option",{value:"OBC",children:"OBC"}),e.jsx("option",{value:"SC/ST",children:"SC/ST"}),e.jsx("option",{value:"Sports Quota",children:"Sports Quota"}),e.jsx("option",{value:"Defence",children:"Defence"})]})})]})}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden",children:[e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-3 px-4",children:"Application ID"}),e.jsx("th",{className:"py-3 px-4",children:"Applicant"}),e.jsx("th",{className:"py-3 px-4",children:"Programme"}),e.jsx("th",{className:"py-3 px-4",children:"Category"}),e.jsx("th",{className:"py-3 px-4",children:"Status"}),e.jsx("th",{className:"py-3 px-4",children:"Submitted"}),e.jsx("th",{className:"py-3 px-4 text-right",children:"Action"})]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9] text-[#12233F]",children:R.length===0?e.jsx("tr",{children:e.jsx("td",{colSpan:7,className:"py-8 text-center text-[#475569]",children:"No applicant records match the selected filters."})}):R.map(w=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors cursor-pointer group",onClick:()=>b(w),children:[e.jsx("td",{className:"py-3 px-4 font-mono font-medium text-[var(--accent)]",children:w.id}),e.jsxs("td",{className:"py-3 px-4",children:[e.jsx("div",{className:"font-semibold text-[#12233F]",children:w.applicant}),e.jsxs("div",{className:"text-[11px] text-[#64748B] flex items-center gap-1",children:[e.jsxs("span",{children:["Rank #",w.meritRank]}),w.sportsDiscipline&&e.jsxs("span",{children:["• ",w.sportsDiscipline]})]})]}),e.jsx("td",{className:"py-3 px-4 text-[#12233F] font-medium",children:w.programme}),e.jsx("td",{className:"py-3 px-4",children:e.jsx("span",{className:"px-2 py-0.5 rounded text-[10px] font-medium bg-[#F1F5F9] text-[var(--accent)]",children:w.category})}),e.jsx("td",{className:"py-3 px-4",children:e.jsxs("span",{className:`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${w.status==="Confirmed"?"bg-[#16834B26] text-[#126B3D]":w.status==="Shortlisted"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-current"}),w.status]})}),e.jsx("td",{className:"py-3 px-4 text-[#475569]",children:w.submitted}),e.jsx("td",{className:"py-3 px-4 text-right",onClick:T=>T.stopPropagation(),children:e.jsx("button",{onClick:()=>b(w),className:"px-3 py-1 rounded-md border border-[#E2E8F0] hover:border-[#9333EA] text-[var(--accent)] font-semibold hover:bg-[#FFFFFF] text-[11px] transition-colors",children:"View →"})})]},w.id))})]})}),e.jsxs("div",{className:"py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]",children:[e.jsxs("span",{children:["Displaying ",e.jsx("strong",{className:"text-[#12233F]",children:R.length})," candidate applications"]}),e.jsx("span",{className:"text-[11px]",children:"Sample data · admissions module not built yet"})]})]}),v&&l&&e.jsxs("div",{className:"fixed inset-0 z-50 overflow-hidden",children:[e.jsx("div",{className:"absolute inset-0 bg-[#12233F]/50 backdrop-blur-xs transition-opacity",onClick:_}),e.jsx("div",{className:"fixed inset-y-0 right-0 max-w-full flex pl-10",children:e.jsxs("div",{className:"w-screen max-w-lg bg-[#FFFFFF] shadow-2xl border-l border-[#E2E8F0] flex flex-col",children:[e.jsxs("div",{className:"p-5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]",children:[e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx("span",{className:"font-mono text-xs px-2 py-0.5 rounded bg-[#7E22CE26] text-[var(--accent)] font-bold",children:l.id}),e.jsx("span",{className:"text-sm font-bold text-[#12233F]",children:"APPLICATION DETAILS"})]}),e.jsx("button",{onClick:_,className:"p-1 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#FFFFFF]",children:e.jsx(ie,{className:"w-5 h-5"})})]}),e.jsxs("div",{className:"flex-1 overflow-y-auto p-6 space-y-6",children:[e.jsxs("div",{className:"p-4 rounded-xl bg-[#F6F8FB] border border-[#E2E8F0] space-y-3",children:[e.jsxs("div",{className:"flex items-start justify-between",children:[e.jsxs("div",{children:[e.jsx("h3",{className:"text-base font-bold text-[#12233F]",children:l.applicant}),e.jsx("p",{className:"text-xs text-[var(--accent)] font-medium",children:l.programme})]}),e.jsx("span",{className:`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${l.status==="Confirmed"?"bg-[#16834B26] text-[#126B3D]":l.status==="Shortlisted"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:l.status})]}),e.jsxs("div",{className:"grid grid-cols-2 gap-2 text-xs pt-2 border-t border-[#E2E8F0]",children:[e.jsxs("div",{children:[e.jsx("span",{className:"text-[#475569] text-[11px]",children:"Quota / Category:"}),e.jsx("p",{className:"font-semibold text-[#12233F]",children:l.category})]}),e.jsxs("div",{children:[e.jsx("span",{className:"text-[#475569] text-[11px]",children:"Merit Rank:"}),e.jsxs("p",{className:"font-semibold text-[#12233F]",children:["Merit Rank #",l.meritRank]})]}),e.jsxs("div",{children:[e.jsx("span",{className:"text-[#475569] text-[11px]",children:"Candidate Contact:"}),e.jsx("p",{className:"font-mono text-[#12233F]",children:l.phone})]}),e.jsxs("div",{children:[e.jsx("span",{className:"text-[#475569] text-[11px]",children:"Email Address:"}),e.jsx("p",{className:"font-mono text-[var(--accent)] truncate",children:l.email})]})]}),l.sportsDiscipline&&e.jsxs("div",{className:"pt-2 border-t border-[#E2E8F0] flex items-center gap-1.5 text-xs text-[var(--accent)]",children:[e.jsx(Ji,{className:"w-3.5 h-3.5 text-[#8A4F00]"}),e.jsx("span",{className:"font-medium",children:"Athletic Discipline:"}),e.jsx("span",{className:"font-semibold",children:l.sportsDiscipline})]})]}),e.jsxs("div",{className:"space-y-3",children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsxs("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider",children:["Uploaded Statutory Documents (",l.documents.length,")"]}),e.jsx("span",{className:"text-[11px] text-[#475569]",children:"Click checkbox to toggle verification"})]}),e.jsx("div",{className:"space-y-2",children:l.documents.map(w=>e.jsxs("div",{onClick:()=>P(w.id),className:`p-3 rounded-lg border flex items-center justify-between transition-colors cursor-pointer ${w.verified?"bg-[#16834B26]/30 border-[#16834B]/30 hover:bg-[#16834B26]/50":"bg-[#DC262614] border-[#DC262640] hover:bg-[#DC262626]"}`,children:[e.jsxs("div",{className:"flex items-center gap-2.5",children:[e.jsx("button",{type:"button",className:`w-5 h-5 rounded flex items-center justify-center transition-colors ${w.verified?"bg-[#16834B] text-white":"border border-[#CBD5E1] bg-[#FFFFFF]"}`,children:w.verified&&e.jsx(We,{className:"w-3.5 h-3.5 stroke-[3]"})}),e.jsxs("div",{children:[e.jsx("p",{className:"text-xs font-semibold text-[#12233F]",children:w.name}),e.jsxs("p",{className:"text-[10px] text-[#475569]",children:["Format: ",w.type," • ",w.fileSize||"size unknown"]})]})]}),e.jsx("span",{className:`text-[10px] font-semibold px-2 py-0.5 rounded ${w.verified?"bg-[#16834B26] text-[#126B3D]":"bg-[#DC262626] text-[#B91C1C]"}`,children:w.verified?"Verified ✓":"Pending Verification"})]},w.id))})]}),e.jsxs("div",{className:"space-y-3",children:[e.jsx("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider",children:"Application Lifecycle Timeline"}),e.jsx("div",{className:"relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#E2E8F0]",children:l.timeline.map((w,T)=>{const M=w.status==="completed",j=w.status==="in-progress";return e.jsxs("div",{className:"relative",children:[e.jsx("div",{className:`absolute -left-6 top-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center ${M?"bg-[#16834B] border-white text-white":j?"bg-[#9333EA] border-white text-white animate-pulse":"bg-[#F1F5F9] border-[#CBD5E1]"}`,children:M&&e.jsx(We,{className:"w-2.5 h-2.5 stroke-[3]"})}),e.jsxs("div",{className:"space-y-0.5",children:[e.jsx("p",{className:"text-xs font-bold text-[#12233F]",children:w.step}),e.jsx("p",{className:"text-[11px] text-[#475569]",children:w.timestamp}),w.note&&e.jsx("p",{className:"text-[11px] text-[var(--accent)] bg-[#7E22CE26]/40 p-1.5 rounded mt-1",children:w.note})]})]},T)})})]})]}),e.jsxs("div",{className:"p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] space-y-2",children:[e.jsxs("div",{className:"grid grid-cols-2 gap-2",children:[e.jsxs("button",{onClick:()=>L(l.id),className:"py-2.5 px-3 rounded-lg border border-[#F39A19] text-[#8A4F00] hover:bg-[#F39A1926]/40 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5",children:[e.jsx(Ze,{className:"w-3.5 h-3.5"}),e.jsx("span",{children:"Request Changes"})]}),e.jsxs("button",{onClick:()=>C(l.id),disabled:l.status==="Confirmed",className:"py-2.5 px-3 rounded-lg bg-[#16834B] hover:bg-[#126B3D] text-white text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-sm disabled:opacity-70",children:[e.jsx(Z,{className:"w-3.5 h-3.5"}),e.jsx("span",{children:"Approve & Admit"})]})]}),e.jsx("p",{className:"text-[10px] text-center text-[#475569]",children:"Sample workflow: changes stay on this page. The admissions module is not built yet."})]})]})})]})]})},Gc=()=>{const[n]=f.useState(vs),[t,s]=f.useState(""),[i,a]=f.useState("All"),[o,m]=f.useState("All"),[p,g]=f.useState(null),u=l=>{g(l),setTimeout(()=>g(null),3e3)},k=n.filter(l=>{const y=l.user.toLowerCase().includes(t.toLowerCase())||l.action.toLowerCase().includes(t.toLowerCase())||l.resource.toLowerCase().includes(t.toLowerCase()),v=i==="All"||l.role===i,x=o==="All"||l.status===o;return y&&v&&x}),h=["All",...Array.from(new Set(n.map(l=>l.role)))];return e.jsxs("div",{className:"space-y-6",children:[p&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs",children:[e.jsx(Z,{className:"w-4 h-4 text-[#126B3D]"}),e.jsx("span",{children:p})]}),e.jsx(ve,{title:"Audit Activity",subtitle:e.jsxs("span",{className:"inline-flex flex-wrap items-center gap-2",children:["Every state change writes to platform/audit, and audit records are immutable (ARCHITECTURE.md). Its API is not built yet, so these are sample events using the event names in the repo's contracts.",e.jsxs("span",{className:"inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#475569]",children:[e.jsx(ze,{className:"w-3 h-3"}),"Sample data"]})]}),actions:e.jsx(e.Fragment,{children:e.jsxs("button",{onClick:()=>u("Export needs the platform/audit API, which is not built yet"),className:je,children:[e.jsx(zn,{className:"w-3.5 h-3.5"}),"Export Audit Log"]})})}),e.jsx(xe,{stats:[{label:"Events today",icon:Zt,value:String(n.filter(l=>!l.timestamp.startsWith("Yesterday")).length),note:"Sample events"},{label:"Successful",icon:Z,value:String(n.filter(l=>l.status==="Success").length),note:"State changes recorded"},{label:"Blocked or failed",icon:rs,value:String(n.filter(l=>l.status!=="Success").length),delta:"review",deltaTone:"alert",note:"Failed or needs review"},{label:"Active actors",icon:tn,value:String(new Set(n.map(l=>l.user)).size),note:"Distinct users and services"}]}),e.jsx("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs",children:e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-3 gap-3",children:[e.jsxs("div",{className:"relative",children:[e.jsx(ye,{className:"w-4 h-4 text-[#475569] absolute left-3 top-2.5"}),e.jsx("input",{type:"text",placeholder:"Search by action, user, or resource ID...",value:t,onChange:l=>s(l.target.value),className:"w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"})]}),e.jsx("div",{children:e.jsxs("select",{value:i,onChange:l=>a(l.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Roles"}),h.filter(l=>l!=="All").map(l=>e.jsx("option",{value:l,children:re(l)},l))]})}),e.jsx("div",{children:e.jsxs("select",{value:o,onChange:l=>m(l.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Event Outcomes"}),e.jsx("option",{value:"Success",children:"Success"}),e.jsx("option",{value:"Failed",children:"Failed"}),e.jsx("option",{value:"Warning",children:"Warning"})]})})]})}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden",children:[e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-3 px-4 w-32",children:"Timestamp"}),e.jsx("th",{className:"py-3 px-4",children:"User"}),e.jsx("th",{className:"py-3 px-4",children:"Role"}),e.jsx("th",{className:"py-3 px-4",children:"Action"}),e.jsx("th",{className:"py-3 px-4",children:"Resource Target"}),e.jsx("th",{className:"py-3 px-4",children:"Status"}),e.jsx("th",{className:"py-3 px-4 text-right",children:"Origin IP"})]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9] text-[#12233F]",children:k.length===0?e.jsx("tr",{children:e.jsx("td",{colSpan:7,className:"py-8 text-center text-[#475569]",children:"No audit records matching search parameters."})}):k.map(l=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors",children:[e.jsx("td",{className:"py-3 px-4 font-mono text-[#475569] whitespace-nowrap",children:l.timestamp}),e.jsx("td",{className:"py-3 px-4 font-semibold text-[#12233F]",children:l.user}),e.jsx("td",{className:"py-3 px-4",children:e.jsx("span",{className:"px-2 py-0.5 rounded text-[10px] font-medium bg-[#F1F5F9] text-[#7E22CE]",children:re(l.role)})}),e.jsx("td",{className:"py-3 px-4 text-[#12233F]",children:l.action}),e.jsx("td",{className:"py-3 px-4 font-mono text-[#7E22CE] font-semibold",children:l.resource}),e.jsx("td",{className:"py-3 px-4",children:e.jsxs("span",{className:`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${l.status==="Success"?"bg-[#16834B26] text-[#126B3D]":l.status==="Warning"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:[l.status==="Success"?e.jsx(Z,{className:"w-3 h-3"}):l.status==="Warning"?e.jsx(Ze,{className:"w-3 h-3"}):e.jsx(ms,{className:"w-3 h-3"}),e.jsx("span",{children:l.status})]})}),e.jsx("td",{className:"py-3 px-4 text-right font-mono text-[11px] text-[#64748B]",children:l.ipAddress})]},l.id))})]})}),e.jsxs("div",{className:"py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]",children:[e.jsxs("span",{children:["Displaying ",e.jsx("strong",{className:"text-[#12233F]",children:k.length})," sequential ledger entries"]}),e.jsx("span",{className:"text-[11px]",children:"platform/audit: append-only by design; API not built yet"})]})]})]})},Ot={planned:"bg-[#F1F5F9] text-[#475569]","in-progress":"bg-[#F39A1926] text-[#8A4F00]",stable:"bg-[#16834B26] text-[#126B3D]",deprecated:"bg-[#F1F5F9] text-[#64748B]"},Zs={included:"bg-[#16834B26] text-[#126B3D]",upgrade:"bg-[#F39A1926] text-[#8A4F00]","not-in-profile":"bg-[#F1F5F9] text-[#64748B]",platform:"bg-[#7E22CE26] text-[#7E22CE]","per-organisation":"bg-[#F1F5F9] text-[#475569]"};function Wc(n){if(!n.entitlement||!n.profile)return`# Super admin: outside every organisation.
# Each organisation's entitlement =
#   academy profile modules ∩ plan (∪ overrides)
`;const t=[...n.entitlement.modules],s=i=>i.length?i.map(a=>`
  - ${a}`).join(""):" []";return`# entitlement = profile modules ∩ plan (∪ overrides)
academy_type: ${n.profile.profile}
plan: ${n.entitlement.plan}
modules:${s(t)}
upgrade_to_unlock:${s(n.entitlement.upgradableModules)}
`}const Yc=()=>{var u,k;const n=Se(),[t,s]=f.useState(""),i=t.trim().toLowerCase(),a=h=>!i||h.name.toLowerCase().includes(i)||h.id.includes(i),o=[...Ne.map(h=>({key:h.id,title:Sn(h),path:`modules/${h.domain}/`,modules:h.modules})),{key:"platform",title:"Shared platform services",path:"platform/",modules:Te},{key:"integrations",title:"External integrations",path:"integrations/",modules:He}].map(h=>({...h,modules:h.modules.filter(a)})).filter(h=>h.modules.length),m=Ne.flatMap(h=>h.modules),p=m.filter(h=>Ie(h,n)==="included").length,g=Xn.filter(h=>h.implemented);return e.jsxs("div",{className:"space-y-6",children:[e.jsx(ve,{title:"Module Registry",subtitle:"Every module in the monorepo. An organisation may use the modules in its academy profile and plan (its entitlement); a super admin can add overrides.",actions:e.jsxs("div",{className:"relative",children:[e.jsx(ye,{className:"w-3.5 h-3.5 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2"}),e.jsx("input",{value:t,onChange:h=>s(h.target.value),placeholder:"Search modules",className:"h-8 pl-8 pr-3 w-56 rounded-full bg-[#F1F5F9] text-xs text-[#12233F] placeholder:text-[#475569] focus:outline-none"})]})}),e.jsx(xe,{stats:[{label:"Feature modules",icon:Jt,value:String(m.length),note:"Suites A–G, Practice and Global Support"},n.entitlement?{label:"In entitlement",icon:Vn,value:String(p),delta:`of ${((u=n.profile)==null?void 0:u.modules.filter(h=>h.includes("/")).length)??0}`,deltaTone:"muted",note:`${(k=n.profile)==null?void 0:k.profile} · ${n.planTitle} plan`}:{label:"In entitlement",icon:Vn,value:"–",note:"Decided per organisation"},{label:"Backend built",icon:qn,value:String(g.length),note:g.map(h=>h.id).join(", ")},{label:"Platform & integrations",icon:Nr,value:String(Te.length+He.length),note:`${Te.length} services · ${He.length} adapters`}]}),e.jsxs("div",{className:"grid grid-cols-1 xl:grid-cols-12 gap-6 items-start",children:[e.jsxs("div",{className:"xl:col-span-8 space-y-5",children:[o.map(h=>e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden",children:[e.jsxs("header",{className:"px-4 py-3 bg-[#F6F8FB] border-b border-[#E2E8F0] flex items-center justify-between gap-2",children:[e.jsx("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F]",children:h.title}),e.jsx("code",{className:"text-[10px] text-[#64748B]",children:h.path})]}),e.jsx("ul",{className:"divide-y divide-[#F1F5F9]",children:h.modules.map(l=>{const y=Ie(l,n);return e.jsxs("li",{className:"px-4 py-3 flex items-center gap-3 hover:bg-[#F6F8FB]",children:[e.jsx("span",{className:"w-1.5 h-8 rounded-full flex-shrink-0",style:{background:hs(l)}}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsxs("div",{className:"flex items-center gap-2 flex-wrap",children:[e.jsx(X,{to:`/modules/${l.id}`,className:"text-xs font-semibold text-[#12233F] hover:text-[#7E22CE]",children:l.name}),e.jsx("span",{className:`text-[10px] px-1.5 py-0.5 rounded font-medium ${Ot[l.status]}`,children:l.status}),l.implemented&&e.jsx("span",{className:`text-[10px] px-1.5 py-0.5 rounded font-medium ${Ot.stable}`,children:"backend built"})]}),e.jsx("p",{className:"text-[11px] text-[#475569] truncate",children:l.description})]}),e.jsx("span",{className:`text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap ${Zs[y]}`,children:fn[y]})]},l.id)})})]},h.key)),o.length===0&&e.jsx("p",{className:"text-center text-xs text-[#475569] py-8",children:"No modules match."})]}),e.jsxs("aside",{className:"xl:col-span-4 xl:sticky xl:top-20 bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4",children:[e.jsxs("h3",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] mb-2 flex items-center gap-1.5",children:[e.jsx(un,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),"Entitlement"]}),e.jsx("pre",{className:"text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto",children:Wc(n)}),e.jsxs("p",{className:"text-[11px] text-[#64748B] mt-2",children:["Computed by platform/tenancy from platform/identity/config/profiles and platform/billing/config/plans.yaml, and enforced per request by the entitlement gate in apps/backend. ",n.source==="preview"&&"Preview: the reference profile on the trial plan."]})]})]})]})},zc=Object.assign({"../../../../../modules/academics/academic-management/frontend/src/widgets/index.ts":ca,"../../../../../modules/academics/examinations/frontend/src/widgets/index.ts":ma,"../../../../../modules/academics/lms/frontend/src/widgets/index.ts":pa,"../../../../../modules/academics/timetable-attendance/frontend/src/widgets/index.ts":ua,"../../../../../modules/campus-life/alumni/frontend/src/widgets/index.ts":ga,"../../../../../modules/campus-life/hostel/frontend/src/widgets/index.ts":ha,"../../../../../modules/campus-life/library/frontend/src/widgets/index.ts":fa,"../../../../../modules/campus-life/placement-career/frontend/src/widgets/index.ts":ya,"../../../../../modules/campus-life/transport/frontend/src/widgets/index.ts":ba,"../../../../../modules/facilities/asset-management/frontend/src/widgets/index.ts":xa,"../../../../../modules/facilities/facility-booking/frontend/src/widgets/index.ts":va,"../../../../../modules/facilities/inventory-equipment/frontend/src/widgets/index.ts":wa,"../../../../../modules/facilities/maintenance/frontend/src/widgets/index.ts":ka,"../../../../../modules/facilities/sports-facilities/frontend/src/widgets/index.ts":_a,"../../../../../modules/finance-operations/budget-grants/frontend/src/widgets/index.ts":ja,"../../../../../modules/finance-operations/e-office/frontend/src/widgets/index.ts":Fa,"../../../../../modules/finance-operations/fees-accounts/frontend/src/widgets/index.ts":Na,"../../../../../modules/finance-operations/hr-payroll/frontend/src/widgets/index.ts":Sa,"../../../../../modules/finance-operations/procurement/frontend/src/widgets/index.ts":Ea,"../../../../../modules/governance/grievance/frontend/src/widgets/index.ts":Aa,"../../../../../modules/governance/iqac-accreditation/frontend/src/widgets/index.ts":Ca,"../../../../../modules/governance/regulatory-reports/frontend/src/widgets/index.ts":Pa,"../../../../../modules/governance/rti/frontend/src/widgets/index.ts":Ra,"../../../../../modules/practice/field-training/frontend/src/widgets/index.ts":Ma,"../../../../../modules/practice/portfolio/frontend/src/widgets/index.ts":Da,"../../../../../modules/practice/productions/frontend/src/widgets/index.ts":Oa,"../../../../../modules/practice/projects/frontend/src/widgets/index.ts":Ta,"../../../../../modules/practice/selection-process/frontend/src/widgets/index.ts":Ba,"../../../../../modules/practice/skill-progress/frontend/src/widgets/index.ts":La,"../../../../../modules/sports/athlete-performance/frontend/src/widgets/index.ts":Ia,"../../../../../modules/sports/sports-nutrition-health/frontend/src/widgets/index.ts":qa,"../../../../../modules/sports/tournament-events/frontend/src/widgets/index.ts":$a,"../../../../../modules/sports/training-video-analysis/frontend/src/widgets/index.ts":Va,"../../../../../modules/student-lifecycle/admissions/frontend/src/widgets/index.ts":Ha,"../../../../../modules/student-lifecycle/enrolment-registration/frontend/src/widgets/index.ts":Ua,"../../../../../modules/student-lifecycle/student-information/frontend/src/widgets/index.ts":Ga,"../../../../../modules/student-lifecycle/web-portal-cms/frontend/src/widgets/index.ts":Wa,"../../../../../modules/support/amc-vendor-support/frontend/src/widgets/index.ts":Ya,"../../../../../modules/support/helpdesk/frontend/src/widgets/index.ts":za,"../../../../../modules/support/incident-management/frontend/src/widgets/index.ts":Ka,"../../../../../modules/support/knowledge-base/frontend/src/widgets/index.ts":Qa,"../../../../../modules/support/sla-management/frontend/src/widgets/index.ts":Ja}),_n=Object.fromEntries(Object.entries(zc).map(([n,t])=>[n.split("/").slice(-5,-4)[0],t.widgets??[]])),Tt={"student-information":{src:B("/students.jpg"),position:"50% 72%"},"enrolment-registration":{src:B("/enrolment.jpg"),position:"40% 60%"},"web-portal-cms":{src:B("/web-portal.jpg"),position:"60% 55%"},"academic-management":{src:B("/academics.jpg"),position:"70% 45%"},lms:{src:B("/lms.jpg"),position:"55% 45%"},"timetable-attendance":{src:B("/timetable.jpg"),position:"50% 40%"},examinations:{src:B("/examinations.jpg"),position:"50% 12%"},"athlete-performance":{src:B("/athletes.jpg"),position:"50% 42%"},"training-video-analysis":{src:B("/training.jpg"),position:"50% 30%"},"sports-nutrition-health":{src:B("/nutrition.jpg"),position:"50% 18%"},"tournament-events":{src:B("/tournaments.jpg"),position:"50% 30%"},"sports-facilities":{src:B("/facilities.jpg"),position:"50% 45%"},"facility-booking":{src:B("/facility-booking.jpg"),position:"50% 40%"},"inventory-equipment":{src:B("/inventory.jpg"),position:"50% 30%"},"asset-management":{src:B("/assets.jpg"),position:"50% 28%"},maintenance:{src:B("/maintenance.jpg"),position:"50% 30%"},"fees-accounts":{src:B("/fees.jpg"),position:"50% 55%"},"budget-grants":{src:B("/budget.jpg"),position:"50% 55%"},procurement:{src:B("/procurement.jpg"),position:"50% 50%"},"hr-payroll":{src:B("/hr-payroll.jpg"),position:"0% 50%"},hostel:{src:B("/hostel.jpg"),position:"50% 25%"},"e-office":{src:B("/e-office.jpg"),position:"50% 25%"},transport:{src:B("/transport.jpg"),position:"50% 25%"},portfolio:{src:B("/portfolio-v3.jpg"),position:"100% 50%"},projects:{src:B("/projects-v2.jpg"),position:"100% 50%"},"selection-process":{src:B("/selection-process.jpg"),position:"100% 50%"},productions:{src:B("/productions.jpg"),position:"100% 50%"},"field-training":{src:B("/field-training.jpg"),position:"100% 50%"},"skill-progress":{src:B("/skill-progress.jpg"),position:"100% 50%"},library:{src:B("/library.jpg"),position:"100% 50%"},alumni:{src:B("/alumni.jpg"),position:"100% 50%"},"placement-career":{src:B("/placement-career.jpg"),position:"100% 50%"},grievance:{src:B("/grievance.jpg"),position:"100% 50%"},rti:{src:B("/rti.jpg"),position:"100% 50%"},"iqac-accreditation":{src:B("/iqac-accreditation.jpg"),position:"100% 50%"}},Kc=(n,t,s)=>n==="feature"?`modules/${t}/${s}`:n==="platform"?`platform/${s}`:`integrations/${s}`,Qc=()=>{const{moduleId:n=""}=ni(),t=Se(),[s,i]=f.useState(null),a=Je(n),o=b=>{i(b),setTimeout(()=>i(null),3e3)};if(!a)return e.jsxs("div",{className:"max-w-xl mx-auto py-16 text-center space-y-4",children:[e.jsxs("h1",{className:"text-xl font-bold text-[#12233F]",children:['Unknown module "',n,'"']}),e.jsx(X,{to:"/modules",className:"text-xs text-[var(--accent)] hover:underline",children:"Back to the module registry"})]});const m=En(a.suiteId),p=Kc(a.kind,m==null?void 0:m.domain,a.id),g=Ie(a,t),u=gs[a.id],k=$d(a.id),h=new Set((_n[a.id]??[]).map(b=>b.id)),l=qd(a.id),y=(an[a.id]??[]).map(b=>b.key),v=b=>Object.entries(Ce).filter(([,_])=>_.has(b)).map(([_])=>_),x=Js[a.id]??Vc(a),F=[ys[a.id]??ns,In,nn,os],E=Xs(a.id,x.chart.base,x.chart.split??0),A=x.chart.series.map((b,_)=>({key:_===0?"a":"b",name:b}));return e.jsxs(Ys,{theme:cc(a.id),className:"space-y-8",children:[s&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs",children:[e.jsx(Z,{className:"w-4 h-4 text-[#4ADE80]"}),e.jsx("span",{children:s})]}),e.jsx(ve,{art:Tt[a.id]?e.jsx(nt,{...Tt[a.id],fit:"right"}):void 0,eyebrow:e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-white"}),m?Sn(m):a.kind==="platform"?"Shared platform service":"External integration"]}),title:a.name,subtitle:e.jsxs(e.Fragment,{children:[a.description,e.jsxs("span",{className:"block text-xs text-[#64748B] mt-0.5",children:[a.implemented?"Backend built · figures below are sample data":"Not built yet: sample data"," · ",fn[g]]})]}),actions:e.jsxs(e.Fragment,{children:[e.jsxs("button",{onClick:()=>o(`${x.action} needs the ${a.name} ${a.implemented?"screens":"module"}, which ${a.implemented?"are":"is"} not built yet`),className:je,children:[e.jsx(as,{className:"w-3.5 h-3.5"}),x.action]}),a.route?e.jsxs(X,{to:a.route,className:ae,children:["Open workflow ",e.jsx(Fe,{className:"w-3.5 h-3.5"})]}):e.jsxs("button",{onClick:()=>o(`Export needs the ${a.name} ${a.implemented?"screens":"module"}, which ${a.implemented?"are":"is"} not built yet`),className:ae,children:[e.jsx(zn,{className:"w-3.5 h-3.5 text-[#475569]"}),"Export"]}),e.jsxs("span",{className:ae,title:"Decided by the organisation's academy profile and plan",children:[e.jsx(Vn,{className:"w-3.5 h-3.5 text-[#475569]"}),fn[g]]})]})}),e.jsx(xe,{stats:x.kpis.map((b,_)=>({label:b.label,icon:F[_],value:b.value,delta:b.delta,deltaTone:b.tone??"up",note:b.note}))}),e.jsx(at,{title:x.chart.title,subtitle:x.chart.subtitle,data:E,xKey:"month",series:x.chart.split?A:A.slice(0,1),tooltipLabel:b=>`${b} 2026`}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsx(it,{title:x.breakdown.title,subtitle:x.breakdown.subtitle,items:x.breakdown.items.map(([b,_])=>({label:b,count:_})),relativeToFirst:!!x.breakdown.footer,unit:x.breakdown.unit,footer:x.breakdown.footer&&{label:x.breakdown.footer[0],value:x.breakdown.footer[1]}}),e.jsx("div",{className:"lg:col-span-2",children:e.jsx(uc,{items:x.actions.map((b,_)=>({id:`${a.id}-a${_}`,...b})),onOpen:b=>o(`${b.ref} is a sample item: the ${a.name} module is not built yet`)})})]}),e.jsx(Ks,{subtitle:`${a.name} audit trail`,items:x.activity.map((b,_)=>({id:`${a.id}-l${_}`,time:b.time,title:b.title,meta:e.jsxs(e.Fragment,{children:[b.who," · ",e.jsx("span",{className:"font-mono",children:b.ref})]}),status:b.status??"Success"}))}),e.jsxs("details",{className:`${z} group`,children:[e.jsxs("summary",{className:"list-none cursor-pointer px-5 py-4 flex items-center justify-between gap-4",children:[e.jsxs("div",{children:[e.jsx("h2",{className:"text-[13px] font-semibold text-[#12233F]",children:"Module details"}),e.jsxs("p",{className:"text-xs text-[#64748B] mt-0.5",children:["Manifest, permission keys and role dashboards · status ",a.status," · ",y.length," keys · ",k.length," widgets (",h.size," built) · on ",l.length," role dashboards"]})]}),e.jsx(en,{className:"w-4 h-4 text-[#64748B] transition-transform group-open:rotate-180"})]}),e.jsx("div",{className:"px-5 pb-5 pt-1",children:e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-2 gap-6",children:[e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-2",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5",children:[e.jsx(un,{className:"w-3.5 h-3.5 text-[var(--accent)]"})," ",p,"/module.yaml"]}),e.jsx("pre",{className:"text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto",children:`name: ${(u==null?void 0:u.name)??a.id}
  kind: ${(u==null?void 0:u.kind)??a.kind}
  domain: ${(u==null?void 0:u.domain)??(m==null?void 0:m.domain)??a.kind}
  tier: ${(u==null?void 0:u.tier)??""}${u!=null&&u.field?`
  field: ${u.field}`:""}
  status: ${(u==null?void 0:u.status)??a.status}
  description: "${a.description}"
  exposes:
    api: contracts/openapi.yaml        # /api/v1/${a.id}
    events: contracts/events.yaml      # ${a.id}.<entity>.<past-verb>
    permissions: contracts/permissions.yaml`}),e.jsx("p",{className:"text-[11px] text-[#64748B]",children:"Other modules reach this one only through these contracts and events, never by importing its code."})]}),e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] p-4 pb-2 flex items-center gap-1.5",children:[e.jsx(Pe,{className:"w-3.5 h-3.5 text-[var(--accent)]"})," Permission keys"]}),e.jsx("table",{className:"w-full text-xs",children:e.jsxs("tbody",{className:"divide-y divide-[#F1F5F9]",children:[y.length===0&&e.jsx("tr",{children:e.jsxs("td",{className:"py-2 px-4 text-[11px] text-[#475569]",children:["None defined yet in ",e.jsxs("span",{className:"font-mono",children:[p,"/contracts/permissions.yaml"]}),"."]})}),y.map(b=>{const _=v(b);return e.jsxs("tr",{children:[e.jsx("td",{className:"py-2 px-4 font-mono text-[11px] text-[#12233F] whitespace-nowrap",children:b}),e.jsx("td",{className:"py-2 px-4 text-[11px] text-[#475569]",children:_.length?_.map(re).join(", "):e.jsx("span",{className:"text-[#64748B]",children:"Not granted to any role yet"})})]},b)})]})}),e.jsx("div",{className:"p-3 border-t border-[#E2E8F0] text-right",children:e.jsx(X,{to:"/roles",className:"text-[11px] text-[var(--accent)] hover:underline",children:"See Roles & Permissions →"})})]}),e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-3",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5",children:[e.jsx(Le,{className:"w-3.5 h-3.5 text-[var(--accent)]"})," Dashboard widgets"]}),k.length?e.jsx("ul",{className:"space-y-1.5",children:k.map(b=>e.jsxs("li",{className:"flex items-center justify-between gap-2 text-[11px]",children:[e.jsx("code",{className:"text-[#334155]",children:b}),e.jsx("span",{className:h.has(b)?"text-[#126B3D]":"text-[#64748B]",children:h.has(b)?"built":"not built yet"})]},b))}):e.jsx("p",{className:"text-[11px] text-[#475569]",children:"No role layout references a widget from this module."}),e.jsxs("p",{className:"text-[11px] text-[#64748B]",children:["Exported from ",p,"/frontend/src/widgets/index.ts"]})]}),e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-3",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5",children:[e.jsx(sn,{className:"w-3.5 h-3.5 text-[var(--accent)]"})," On these role dashboards"]}),l.length?e.jsx("div",{className:"flex flex-wrap gap-1.5",children:l.map(b=>e.jsx(X,{to:`/dashboards?role=${b}`,className:"text-[11px] px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155] hover:border-[#9333EA] hover:text-[#12233F]",children:re(b)},b))}):e.jsx("p",{className:"text-[11px] text-[#475569]",children:"None yet."})]})]})})]})]})},Jc={"1x1":"sm:col-span-1","2x1":"sm:col-span-2","2x2":"sm:col-span-2 sm:row-span-2",full:"sm:col-span-2"},Xc=()=>{const[n,t]=Wt(),s=Se(),{ROLES:i,ROLE_LAYOUTS:a,ROLES_PROFILE_TITLE:o}=et(),m=Object.keys(a),p=n.get("role")&&a[n.get("role")]?n.get("role"):"management",g=i.find(y=>y.id===p),u=a[p],k=f.useMemo(()=>{const y=new Set(g.permissions);return qe(p).map(v=>{var b;const x=Ue(v),F=(b=_n[x])==null?void 0:b.find(_=>_.id===v);if(!F)return{id:v,state:{kind:"not-built"}};const E=Je(x),A=E?Ie(E,s):"not-in-profile";return A==="upgrade"?{id:v,state:{kind:"disabled",reason:"Not in this organisation's plan"}}:A==="not-in-profile"?{id:v,state:{kind:"disabled",reason:"Not in this academy profile"}}:y.has(F.permission)?{id:v,state:{kind:"ready",widget:F}}:{id:v,state:{kind:"hidden",permission:F.permission}}})},[p,g,s]),h=k.filter(y=>y.state.kind==="ready").length,l=m.map(y=>{const v=qe(y),x=v.filter(F=>{var E;return(E=_n[Ue(F)])==null?void 0:E.some(A=>A.id===F)}).length;return{id:y,total:v.length,done:x}});return e.jsxs("div",{className:"space-y-6",children:[e.jsx(ve,{title:"Role Dashboards",subtitle:e.jsxs(e.Fragment,{children:["One dashboard page, ",m.length," layouts (",o," profile and platform roles). Each role's widgets are listed in"," ",e.jsx("code",{className:"text-[#6B21A8]",children:"platform/identity/config/dashboards/<role>.yaml"}),"."]}),actions:e.jsxs("label",{className:"text-xs text-[#334155] flex items-center gap-2",children:["View as",e.jsx("select",{value:p,onChange:y=>t({role:y.target.value}),className:"h-8 px-3 rounded-md bg-[#FFFFFF] border border-[#E2E8F0] text-xs text-[#12233F] focus:outline-none focus:border-[#CBD5E1]",children:m.map(y=>e.jsx("option",{value:y,children:a[y].title},y))})]})}),e.jsx(xe,{stats:[{label:"Widgets on this dashboard",icon:Le,value:String(k.length),note:u.title},{label:"Live",icon:Z,value:String(h),note:"Built and permitted"},{label:"Not built yet",icon:qn,value:String(k.filter(y=>y.state.kind==="not-built").length),deltaTone:"alert",note:"No module exports these widgets yet"},{label:"Coverage, all roles",icon:un,value:`${Math.round(l.reduce((y,v)=>y+v.done,0)/Math.max(1,l.reduce((y,v)=>y+v.total,0))*100)}%`,note:`Widgets built across ${m.length} layouts`}]}),e.jsxs("div",{className:"grid grid-cols-1 xl:grid-cols-12 gap-6 items-start",children:[e.jsxs("section",{className:"xl:col-span-8 space-y-3","aria-label":`${u.title} dashboard`,children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("h2",{className:"text-sm font-bold text-[#12233F]",children:u.title}),e.jsxs("span",{className:"text-[11px] text-[#475569]",children:[h," of ",k.length," widgets live"]})]}),e.jsx("div",{className:"grid grid-cols-1 sm:grid-cols-4 gap-3 auto-rows-[minmax(130px,auto)]",children:k.map(({id:y,state:v})=>{const x=Je(Ue(y)),F=v.kind==="ready"?v.widget.size:"1x1",E=x?hs(x):"#64748B";return e.jsxs("article",{className:`rounded-xl border p-4 flex flex-col gap-2 ${Jc[F]} ${v.kind==="ready"?"bg-[#FFFFFF] border-[#E2E8F0]":"bg-[#FFFFFF] border-dashed border-[#CBD5E1]"}`,children:[e.jsxs("header",{className:"flex items-start justify-between gap-2",children:[e.jsx("h3",{className:"text-xs font-semibold text-[#12233F] leading-snug",children:v.kind==="ready"?v.widget.title:y}),e.jsx("span",{className:"w-2 h-2 rounded-full mt-1 flex-shrink-0",style:{background:E}})]}),e.jsxs("div",{className:"flex-1",children:[v.kind==="ready"&&e.jsx(v.widget.component,{role:p}),v.kind==="not-built"&&e.jsxs("p",{className:"text-[11px] text-[#475569] flex items-center gap-1.5",children:[e.jsx(qn,{className:"w-3.5 h-3.5"})," Not built yet"]}),v.kind==="disabled"&&e.jsxs("p",{className:"text-[11px] text-[#8A4F00] flex items-center gap-1.5",children:[e.jsx(Sr,{className:"w-3.5 h-3.5"})," ",v.reason]}),v.kind==="hidden"&&e.jsxs("p",{className:"text-[11px] text-[#B91C1C] flex items-center gap-1.5",children:[e.jsx(mr,{className:"w-3.5 h-3.5"})," Hidden: role lacks ",e.jsx("code",{children:v.permission})]})]}),x&&e.jsxs(X,{to:`/modules/${x.id}`,className:"text-[10px] font-mono text-[#64748B] hover:text-[#7E22CE] truncate",children:[x.id,v.kind==="ready"||v.kind==="hidden"?` · needs ${v.kind==="ready"?v.widget.permission:v.permission}`:""]})]},y)})})]}),e.jsxs("aside",{className:"xl:col-span-4 space-y-4",children:[e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4",children:[e.jsxs("h3",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] mb-2 flex items-center gap-1.5",children:[e.jsx(un,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),u.role,".yaml"]}),e.jsx("pre",{className:"text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto",children:`role: ${u.role}
title: "${u.title}"${u.extends?`
extends: ${u.extends}`:""}
widgets:
${u.widgets.map(y=>`  - ${y}`).join(`
`)}`})]}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden",children:[e.jsx("h3",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] p-4 pb-2",children:"Widget coverage by role"}),e.jsx("table",{className:"w-full text-xs",children:e.jsx("tbody",{className:"divide-y divide-[#F1F5F9]",children:l.map(y=>e.jsxs("tr",{onClick:()=>t({role:y.id}),className:`cursor-pointer hover:bg-[#F6F8FB] ${y.id===p?"bg-[#7E22CE26]":""}`,children:[e.jsx("td",{className:"py-2 px-4 text-[#12233F]",children:a[y.id].title}),e.jsxs("td",{className:"py-2 px-4 text-right text-[#475569] whitespace-nowrap",children:[y.done," / ",y.total]})]},y.id))})})]})]})]})]})},Ee="w-full px-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]",W=({label:n,children:t,muted:s})=>e.jsxs("div",{className:"px-5 py-3 flex items-start justify-between gap-4 text-xs",children:[e.jsx("span",{className:"text-[#64748B] flex-shrink-0",children:n}),e.jsx("span",{className:`text-right min-w-0 ${s?"text-[#64748B]":"text-[#12233F] font-semibold"}`,style:{overflowWrap:"anywhere"},children:t})]}),Ve=({children:n="Not available yet"})=>e.jsx("span",{className:"inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#475569] whitespace-nowrap",children:n}),Ae=({label:n,error:t,hint:s,children:i})=>e.jsxs("label",{className:"block",children:[e.jsx("span",{className:"block text-xs font-semibold text-[#12233F] mb-1.5",children:n}),i,t?e.jsx("span",{role:"alert",className:"block mt-1 text-[11px] text-[#B91C1C]",children:t}):s&&e.jsx("span",{className:"block mt-1 text-[11px] text-[#64748B]",children:s})]});function Zc(n){const t={};return n.firstName.trim()||(t.firstName="First name is required."),n.lastName.trim()||(t.lastName="Last name is required."),n.displayName.trim().length>60&&(t.displayName="Keep the display name under 60 characters."),n.phone&&!/^\+?[0-9 ()-]{7,20}$/.test(n.phone.trim())&&(t.phone="Enter a valid phone number, e.g. +91 98765 43210."),n.jobTitle.trim().length>80&&(t.jobTitle="Keep the job title under 80 characters."),n.bio.length>300&&(t.bio=`${n.bio.length}/300 characters: please shorten.`),t}const em=()=>{const{session:n,preview:t,signOut:s}=me(),i=Fn(),a=Se(),o=!n,m=(n==null?void 0:n.me)??{id:"preview",email:"admin@example.org",name:"Administrator",roles:["org-admin"],is_super_admin:!1,permissions:Qn(["org-admin"])},p=(n==null?void 0:n.organisation)??null,g=(p==null?void 0:p.country)??null,u=m.is_super_admin?"super-admin":m.roles[0]??"org-admin",k=a.profile?Qe(a.profile):"–",h=(p==null?void 0:p.name)??(o?"Demo organisation":m.is_super_admin?"Education OS platform":"–"),[l,y]=js(m.id),[v,...x]=m.name.split(/\s+/).filter(Boolean),F={firstName:l.firstName||v||"",lastName:l.lastName||x.join(" "),displayName:l.displayName,phone:l.phone,jobTitle:l.jobTitle,bio:l.bio},E=F.displayName||[F.firstName,F.lastName].filter(Boolean).join(" ")||m.name||m.email,[A,b]=f.useState(!1),[_,C]=f.useState(F),[L,P]=f.useState({}),[R,w]=f.useState(null),T=f.useRef(null),[M,j]=f.useState(null),[O,H]=f.useState(!1),[oe,J]=f.useState(null),U=M??l.photo,V=(I,$)=>{w({ok:I,text:$}),window.setTimeout(()=>w(null),3500)},te=(I,$)=>{try{return y({...l,...I}),V(!0,$),!0}catch{return V(!1,"Could not save: this browser is blocking storage (private window or storage full)."),!1}},G=()=>{C(F),P({}),b(!0)},ee=I=>{I.preventDefault();const $=Zc(_);if(P($),Object.keys($).length)return;const S=Object.fromEntries(Object.entries(_).map(([D,q])=>[D,q.trim()]));te(S,"Profile details saved on this device")&&b(!1)},pe=async I=>{if(I){J(null),H(!0);try{j(await Dd(I))}catch($){J($ instanceof Error?$.message:"This image could not be used.")}finally{H(!1),T.current&&(T.current.value="")}}},we=()=>{M&&te({photo:M},"Profile photo saved on this device")&&j(null)},ue=()=>{j(null),l.photo&&window.confirm("Remove your profile photo?")&&te({photo:null},"Profile photo removed")},le=Intl.DateTimeFormat().resolvedOptions().timeZone,de=typeof navigator<"u"?navigator.language:"en";return e.jsxs("div",{className:"space-y-6",children:[R&&e.jsxs("div",{role:"status",className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs",children:[R.ok?e.jsx(Z,{className:"w-4 h-4 text-[#6FCF97]"}):e.jsx(Ze,{className:"w-4 h-4",style:{color:"#F39A19"}}),e.jsx("span",{children:R.text})]}),e.jsx("header",{className:"eos-hero relative rounded-xl px-6 py-7 sm:px-8 text-white overflow-hidden",children:e.jsxs("div",{className:"relative z-10 flex flex-col md:flex-row md:items-center gap-5",children:[e.jsxs("div",{className:"relative flex-shrink-0 self-start",children:[e.jsx("div",{className:"rounded-full overflow-hidden flex items-center justify-center text-2xl font-bold shadow-lg",style:{width:96,height:96,background:U?"#FFFFFF":"#D03F1B",boxShadow:"0 0 0 4px rgba(255,255,255,0.35)"},children:U?e.jsx("img",{src:U,alt:"Profile photo",className:"w-full h-full",style:{objectFit:"cover"}}):Cn(E)}),e.jsx("button",{type:"button",onClick:()=>{var I;return(I=T.current)==null?void 0:I.click()},"aria-label":"Change profile photo",title:"Change profile photo",className:"absolute bottom-0 right-0 w-8 h-8 rounded-full bg-white text-[#7E22CE] flex items-center justify-center shadow-lg",children:e.jsx(Ir,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsxs("div",{className:"eos-hero-sub text-[12px] font-medium mb-1 inline-flex items-center gap-1.5",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-white"}),re(u)]}),e.jsx("h1",{className:"text-[32px] leading-tight font-bold tracking-[-0.02em] text-white truncate",children:E}),e.jsxs("p",{className:"eos-hero-sub text-[14px] mt-1 truncate",children:[F.jobTitle?`${F.jobTitle} · `:"",h]}),e.jsxs("div",{className:"mt-3 flex flex-wrap items-center gap-2",children:[e.jsxs("span",{className:"inline-flex items-center gap-1.5 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-white text-[#126B3D]",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-[#16834B]"}),o?"Preview":"Active"]}),e.jsx("span",{className:"text-[11px] font-semibold px-2 py-0.5 rounded-full",style:{background:"rgba(255,255,255,0.16)"},children:k})]})]}),e.jsx("div",{className:"flex flex-wrap gap-2.5",children:e.jsxs("button",{type:"button",onClick:G,className:je,children:[e.jsx(gt,{className:"w-3.5 h-3.5"}),"Edit Profile"]})})]})}),e.jsx("input",{ref:T,type:"file",accept:"image/jpeg,image/png,image/webp",className:"hidden","aria-label":"Profile photo file",onChange:I=>{var $;return pe(($=I.target.files)==null?void 0:$[0])}}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsxs("section",{className:`${z} eos-lift`,children:[e.jsx(K,{title:"Profile Photo",subtitle:`JPG, PNG or WebP · up to ${Fs/1048576} MB`}),e.jsxs("div",{className:"px-5 pb-5 flex flex-col items-center gap-4",children:[e.jsx("div",{className:"rounded-full overflow-hidden flex items-center justify-center font-bold text-white",style:{fontSize:30,width:120,height:120,background:U?"#F6F8FB":"#D03F1B",boxShadow:M?"0 0 0 3px #9333EA":"0 0 0 1px #E2E8F0"},children:O?e.jsx("span",{className:"w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin","aria-label":"Processing image"}):U?e.jsx("img",{src:U,alt:M?"New photo preview":"Profile photo",className:"w-full h-full",style:{objectFit:"cover"}}):Cn(E)}),M&&e.jsx("p",{className:"text-[11px] font-semibold text-[#7E22CE]",children:"Preview: not saved yet"}),oe&&e.jsx("p",{role:"alert",className:"w-full rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]",children:oe}),e.jsx("div",{className:"flex flex-wrap justify-center gap-2",children:M?e.jsxs(e.Fragment,{children:[e.jsxs("button",{type:"button",onClick:we,className:je,children:[e.jsx(ut,{className:"w-3.5 h-3.5"}),"Save Photo"]}),e.jsxs("button",{type:"button",onClick:()=>j(null),className:ae,children:[e.jsx(ie,{className:"w-3.5 h-3.5"}),"Cancel"]})]}):e.jsxs(e.Fragment,{children:[e.jsxs("button",{type:"button",onClick:()=>{var I;return(I=T.current)==null?void 0:I.click()},disabled:O,className:ae,children:[e.jsx(qr,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),l.photo?"Replace":"Upload"]}),l.photo&&e.jsxs("button",{type:"button",onClick:ue,className:ae,children:[e.jsx($r,{className:"w-3.5 h-3.5 text-[#B91C1C]"}),"Remove"]})]})}),e.jsx("p",{className:"text-[11px] text-[#64748B] text-center",children:"Saved on this device. Photo storage needs platform/documents, which is not built yet."})]})]}),e.jsxs("section",{className:`${z} lg:col-span-2 eos-lift`,children:[e.jsx(K,{title:"Personal Information",subtitle:A?"Edit your details, then save":"Your details as people in your organisation see them",action:!A&&e.jsxs("button",{type:"button",onClick:G,className:"inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:opacity-80 pt-0.5",children:[e.jsx(gt,{className:"w-3.5 h-3.5"}),"Edit"]})}),A?e.jsxs("form",{onSubmit:ee,noValidate:!0,className:"px-5 pb-5 space-y-4 page-enter",children:[e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 gap-4",children:[e.jsx(Ae,{label:"First Name *",error:L.firstName,children:e.jsx("input",{className:Ee,value:_.firstName,onChange:I=>C({..._,firstName:I.target.value}),autoFocus:!0})}),e.jsx(Ae,{label:"Last Name *",error:L.lastName,children:e.jsx("input",{className:Ee,value:_.lastName,onChange:I=>C({..._,lastName:I.target.value})})}),e.jsx(Ae,{label:"Display Name",error:L.displayName,hint:"Leave empty to use your full name.",children:e.jsx("input",{className:Ee,value:_.displayName,onChange:I=>C({..._,displayName:I.target.value})})}),e.jsx(Ae,{label:"Email",hint:"Your sign-in email. Changing it is not in the identity API yet.",children:e.jsx("input",{className:Ee,style:{opacity:.7,cursor:"not-allowed"},value:m.email,readOnly:!0,"aria-readonly":!0})}),e.jsx(Ae,{label:"Phone Number",error:L.phone,children:e.jsx("input",{className:Ee,type:"tel",value:_.phone,onChange:I=>C({..._,phone:I.target.value}),placeholder:"+91 98765 43210"})}),e.jsx(Ae,{label:"Job Title / Designation",error:L.jobTitle,children:e.jsx("input",{className:Ee,value:_.jobTitle,onChange:I=>C({..._,jobTitle:I.target.value}),placeholder:"e.g. Registrar"})})]}),e.jsx(Ae,{label:"Bio",error:L.bio,hint:`${_.bio.length}/300`,children:e.jsx("textarea",{className:Ee,rows:3,value:_.bio,onChange:I=>C({..._,bio:I.target.value})})}),e.jsxs("div",{className:"flex flex-wrap items-center justify-between gap-3 pt-1",children:[e.jsx("p",{className:"text-[11px] text-[#64748B]",children:"Saved on this device until profile editing is added to platform/identity."}),e.jsxs("div",{className:"flex gap-2",children:[e.jsxs("button",{type:"button",onClick:()=>b(!1),className:ae,children:[e.jsx(ie,{className:"w-3.5 h-3.5"}),"Cancel"]}),e.jsxs("button",{type:"submit",className:je,children:[e.jsx(ut,{className:"w-3.5 h-3.5"}),"Save Changes"]})]})]})]}):e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 border-t border-[#F1F5F9]",children:[e.jsxs("div",{className:"divide-y divide-[#F1F5F9]",children:[e.jsx(W,{label:"First Name",children:F.firstName||"–"}),e.jsx(W,{label:"Last Name",children:F.lastName||"–"}),e.jsx(W,{label:"Display Name",muted:!F.displayName,children:F.displayName||"Not set"}),e.jsx(W,{label:"Email",children:m.email})]}),e.jsxs("div",{className:"divide-y divide-[#F1F5F9]",children:[e.jsx(W,{label:"Phone Number",muted:!F.phone,children:F.phone||"Not set"}),e.jsx(W,{label:"Job Title",muted:!F.jobTitle,children:F.jobTitle||"Not set"}),e.jsx(W,{label:"Bio",muted:!F.bio,children:F.bio||"Not set"}),e.jsx(W,{label:"Last updated",muted:!0,children:l.updatedAt?new Date(l.updatedAt).toLocaleString("en-IN"):"Never"})]})]})]})]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-2 gap-6",children:[e.jsxs("section",{className:`${z} eos-lift`,children:[e.jsx(K,{title:"Organisation Information",subtitle:"platform/tenancy · read-only"}),e.jsxs("div",{className:"px-5 pb-3 flex items-center gap-3",children:[e.jsx("span",{className:"rounded-xl flex items-center justify-center text-sm font-bold text-white flex-shrink-0",style:{width:44,height:44,background:"var(--hero-gradient)"},children:Cn(h)}),e.jsxs("div",{className:"min-w-0",children:[e.jsx("p",{className:"text-[13px] font-semibold text-[#12233F] truncate",children:h}),e.jsx("p",{className:"text-[11px] text-[#64748B]",children:"Logo upload needs platform/documents (not built)"})]})]}),e.jsxs("div",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:[e.jsx(W,{label:"Organisation Name",children:h}),e.jsx(W,{label:"Organisation Type",children:k}),e.jsx(W,{label:"Short Name",children:e.jsx("span",{className:"font-mono text-[11px] font-normal",children:(p==null?void 0:p.slug)??"–"})}),e.jsx(W,{label:"Country",muted:!g,children:g??"Not recorded"}),e.jsx(W,{label:"Organisation Email",muted:!0,children:"Not recorded"}),e.jsx(W,{label:"Organisation Phone",muted:!0,children:"Not recorded"}),e.jsx(W,{label:"Website",muted:!0,children:"Not recorded"}),e.jsx(W,{label:"Address · City · State",muted:!0,children:"Not recorded"})]}),e.jsxs("p",{className:"px-5 py-3 text-[11px] text-[#64748B] border-t border-[#F1F5F9]",children:["Read-only: editing (",e.jsx("code",{children:"PATCH /tenancy/organisation"}),") is in the tenancy contract but not built yet, and the organisation record has no contact or address fields."]})]}),e.jsxs("div",{className:"space-y-6",children:[e.jsxs("section",{className:`${z} eos-lift`,children:[e.jsx(K,{title:"Role & Access",subtitle:"Assigned by your organisation; you cannot change your own role",action:e.jsx(X,{to:"/access",className:"text-xs font-medium text-[var(--accent)] hover:underline pt-0.5",children:"Details"})}),e.jsxs("div",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:[e.jsx(W,{label:"Role",children:e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx(be,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),re(u)]})}),e.jsx(W,{label:"Scope",children:m.is_super_admin?"All organisations":`${h} only`}),e.jsx(W,{label:"Permission keys",children:e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx(Pe,{className:"w-3.5 h-3.5 text-[#475569]"}),m.permissions.length]})})]})]}),e.jsxs("section",{className:`${z} eos-lift`,children:[e.jsx(K,{title:"Security",subtitle:"Sign-in is email and password (platform/identity)"}),e.jsxs("div",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:[e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs",children:[e.jsxs("span",{className:"inline-flex items-center gap-2 text-[#12233F] font-semibold",children:[e.jsx(ts,{className:"w-3.5 h-3.5 text-[#475569]"}),"Change Password"]}),e.jsx(Ve,{})]}),e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs",children:[e.jsxs("span",{className:"inline-flex items-center gap-2 text-[#12233F] font-semibold",children:[e.jsx(Hr,{className:"w-3.5 h-3.5 text-[#475569]"}),"Two-Factor Authentication"]}),e.jsx(Ve,{})]}),e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs",children:[e.jsxs("span",{className:"inline-flex items-center gap-2 text-[#12233F] font-semibold",children:[e.jsx(Me,{className:"w-3.5 h-3.5 text-[#475569]"}),"This device"]}),e.jsxs("button",{type:"button",onClick:()=>{s(),i("/login",{replace:!0})},className:"inline-flex items-center gap-1 text-xs font-semibold text-[#B91C1C] hover:opacity-80",children:[e.jsx(ss,{className:"w-3.5 h-3.5"}),"Sign out"]})]}),e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs",children:[e.jsx("span",{className:"text-[#475569]",children:"Sign out other devices"}),e.jsx(Ve,{})]})]})]})]})]}),e.jsxs("section",{className:`${z} eos-lift`,children:[e.jsx(K,{title:"Notifications & Preferences",subtitle:"Notification settings need platform/notification, which is not built yet"}),e.jsx("div",{className:"grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 border-t border-[#F1F5F9]",children:[{icon:Vr,label:"Email notifications",value:e.jsx(Ve,{})},{icon:Qt,label:"Important system notices",value:e.jsx(Ve,{})},{icon:Ur,label:"Language",value:e.jsxs("span",{className:"text-[#12233F] font-semibold",children:[de," (browser)"]})},{icon:nn,label:"Time zone",value:e.jsxs("span",{className:"text-[#12233F] font-semibold text-right",style:{overflowWrap:"anywhere"},children:[le," (browser)"]})},{icon:Gr,label:"Theme",value:e.jsx("span",{className:"text-[#12233F] font-semibold",children:"Light"})}].map(({icon:I,label:$,value:S})=>e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs border-b border-[#F1F5F9]",children:[e.jsxs("span",{className:"inline-flex items-center gap-2 text-[#475569] flex-shrink-0",children:[e.jsx(I,{className:"w-3.5 h-3.5"}),$]}),S]},$))})]}),t&&e.jsx("p",{className:"text-[11px] text-[#64748B] text-center",children:"Preview mode: sample account, no API connected."})]})},nm=`from __future__ import annotations

from datetime import datetime

from eos_core.db import get_db
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import BillingError

router = APIRouter(tags=["billing"])


def _err(e: BillingError):
    return HTTPException(e.status, str(e))


class Upgrade(BaseModel):
    plan: str
    billing_cycle: str = "monthly"


class PlanBody(BaseModel):
    id: str
    title: str
    description: str = ""
    price_per_month: float = 0
    currency: str = "INR"
    trial_days: int | None = None
    suites: list[str] = []
    modules: list[str] = []
    specialized_suites: int | str = 0
    integrations: list[str] = []
    limits: dict = {}
    after_trial: str = "read_only"
    published: bool = True


class AdminSet(BaseModel):
    plan: str | None = None
    trial_ends_at: datetime | None = None
    comped_until: datetime | None = None
    reason: str = ""


@router.get("/plans")
def plans(db: Session = Depends(get_db)):
    """Public: the published price list, shown on the sign-up page before anyone has an account."""
    return service.list_plans(db)


@router.get("/subscription")
def subscription(
    p: Principal = Depends(require("billing:subscription:read", organisation=True)), db: Session = Depends(get_db)
):
    sub = service.get_subscription(db, p.organisation_id)
    if not sub:
        raise HTTPException(404, "no subscription")
    return sub.to_dict()


@router.get("/invoices")
def invoices(
    p: Principal = Depends(require("billing:subscription:read", organisation=True)), db: Session = Depends(get_db)
):
    """Invoices of the caller's organisation, newest first (one per paid period)."""
    return service.list_invoices(db, p.organisation_id)


@router.post("/subscription/upgrade", status_code=201)
def upgrade(
    body: Upgrade, p: Principal = Depends(require("billing:subscription:manage")), db: Session = Depends(get_db)
):
    try:
        return service.upgrade(
            db, organisation_id=p.organisation_id, plan_id=body.plan, billing_cycle=body.billing_cycle
        )
    except BillingError as e:
        raise _err(e) from e


@router.post("/subscription/cancel", status_code=204)
def cancel(p: Principal = Depends(require("billing:subscription:manage")), db: Session = Depends(get_db)):
    try:
        service.cancel(db, organisation_id=p.organisation_id)
    except BillingError as e:
        raise _err(e) from e


@router.post("/webhooks/payment", status_code=204)
def payment_webhook(body: dict, db: Session = Depends(get_db)):
    """Payment adapter callback. The adapter verifies the signature before calling this."""
    try:
        service.confirm_payment(db, reference=body.get("reference", ""))
    except BillingError as e:
        raise _err(e) from e


@router.get("/admin/plans")
def admin_plans(p: Principal = Depends(require("platform:plans:manage")), db: Session = Depends(get_db)):
    return service.list_plans(db, include_unpublished=True)


@router.put("/admin/plans/{plan_id}")
def admin_put_plan(
    plan_id: str,
    body: PlanBody,
    p: Principal = Depends(require("platform:plans:manage")),
    db: Session = Depends(get_db),
):
    from ..domain.models import Plan

    plan = db.get(Plan, plan_id) or Plan(id=plan_id)
    for k, v in body.model_dump().items():
        if k == "id":
            continue
        setattr(plan, k, str(v) if k == "specialized_suites" else v)
    db.add(plan)
    db.commit()
    return plan.to_dict()


@router.put("/admin/subscriptions/{org_id}")
def admin_subscription(
    org_id: str,
    body: AdminSet,
    p: Principal = Depends(require("platform:subscriptions:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.admin_set(
            db,
            organisation_id=org_id,
            plan_id=body.plan,
            trial_ends_at=body.trial_ends_at,
            comped_until=body.comped_until,
            reason=body.reason,
        ).to_dict()
    except BillingError as e:
        raise _err(e) from e
`,tm=`"""HTTP surface of event-bus, following contracts/openapi.yaml: an operator view of the outbox. Modules never
publish through it; they call eos_core.events.publish() inside their own transaction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal

from eos_core.db import get_db
from eos_core.tenant import platform_scope
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..application import events
from ..infrastructure.config import EventBusConfig

router = APIRouter(tags=["event-bus"])

ADMIN = "platform:event-bus:admin"


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except events.EventBusError as e:
        raise HTTPException(e.status, e.detail) from e


@contextmanager
def _scope(p: Principal, organisation_id: str | None = None) -> Iterator[events.Scope]:
    """The super admin reads in platform scope (every organisation, or one); anyone else only their own."""
    if p.super_admin and p.can(ADMIN):
        with platform_scope():
            yield events.Scope(organisation_id, every_organisation=True)
        return
    if not p.organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    yield events.Scope(p.organisation_id)


@router.get("/events")
def list_events(
    name: str | None = Query(None, max_length=121),
    state: Literal["pending", "published", "dead_lettered"] | None = None,
    organisation_id: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require("event-bus:event:read")),
    db: Session = Depends(get_db),
):
    config = EventBusConfig.from_env()
    with _scope(p, organisation_id) as scope:
        rows, total = events.list_events(
            db,
            scope,
            config,
            name=name,
            state=state,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
            offset=offset,
        )
        return {"items": [events.event_out(r, config) for r in rows], "total": total}


@router.get("/events/{event_id}")
def get_event(event_id: str, p: Principal = Depends(require("event-bus:event:read")), db: Session = Depends(get_db)):
    config = EventBusConfig.from_env()
    with _scope(p) as scope, _http_errors():
        return events.event_out(events.get_event(db, scope, event_id), config)


@router.post("/events/{event_id}/replay", status_code=202)
def replay_event(
    event_id: str, p: Principal = Depends(require("event-bus:event:replay")), db: Session = Depends(get_db)
):
    config = EventBusConfig.from_env()
    with _scope(p) as scope, _http_errors():
        return events.event_out(events.replay(db, scope, config, event_id, actor=p.user_id), config)


@router.get("/relay/health")
def relay_health(p: Principal = Depends(require("event-bus:relay:read")), db: Session = Depends(get_db)):
    """Backlog across every organisation, so platform-level: only the super admin holds the key."""
    config = EventBusConfig.from_env()
    with platform_scope():
        return events.health(db, config, transport=config.transport)
`,sm=`from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..application import service
from .deps import Principal, current_principal, require

router = APIRouter(tags=["identity"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organisation_slug: str | None = None


class LoginResponse(BaseModel):
    token: str
    user: dict


class CreateUser(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    roles: list[str] = Field(default_factory=lambda: ["student"])


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, token = service.authenticate(
            db, email=body.email, password=body.password, organisation_slug=body.organisation_slug
        )
    except service.AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return {"token": token, "user": user.to_dict()}


class OIDCCallback(BaseModel):
    """What the web shell holds when the provider sends it back: the code from the query string, the PKCE
    verifier it generated, the redirect URI it used and the organisation slug it typed."""

    code: str = Field(min_length=1)
    code_verifier: str = Field(min_length=43, max_length=128)
    redirect_uri: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=40)


@router.get("/auth/oidc/config")
def oidc_config(slug: str = Query(min_length=1, max_length=40), db: Session = Depends(get_db)):
    """ADR-0006: the realm, endpoints, client id and PKCE parameters for "Continue with your institution".
    Public and secret-free. 404 when the organisation has no realm, so the shell shows no button."""
    cfg = service.oidc_config(db, slug)
    if cfg is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "OIDC is not configured for this organisation")
    return cfg


@router.post("/auth/oidc/callback", response_model=LoginResponse)
def oidc_callback(body: OIDCCallback, db: Session = Depends(get_db)):
    """Finish the authorization code flow and answer like /auth/login: the platform's own token. A person the
    provider knows but identity does not gets 403 \`no_account\` (ADR-0006 decision 4)."""
    try:
        user, token = service.authenticate_oidc(
            db, slug=body.slug, code=body.code, code_verifier=body.code_verifier, redirect_uri=body.redirect_uri
        )
    except service.OIDCNotConfiguredError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e
    except service.NoAccountError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_account") from e
    except service.AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    return {"token": token, "user": user.to_dict()}


@router.get("/auth/me")
def me(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    user = service.get_user(db, p.user_id)
    return {**user.to_dict(), "permissions": sorted(p.permissions), "impersonated_by": p.impersonated_by}


@router.get("/users")
def list_users(p: Principal = Depends(require("identity:user:read", organisation=True)), db: Session = Depends(get_db)):
    return [u.to_dict() for u in service.list_users(db)]


@router.post("/users", status_code=201)
def create_user(
    body: CreateUser,
    p: Principal = Depends(require("identity:user:manage", organisation=True)),
    db: Session = Depends(get_db),
):
    if any(r in ("super-admin",) for r in body.roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "platform roles are never grantable inside an organisation")
    try:
        user = service.create_user(
            db,
            organisation_id=p.organisation_id,
            email=body.email,
            name=body.name,
            password=body.password,
            roles=body.roles,
        )
    except service.RoleNotAssignableError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    db.commit()
    return user.to_dict()
`,am=`"""HTTP surface of notification, following contracts/openapi.yaml (merged 0.1.0).

Deliberately NOT here: POST /messages/{id}/resend. The contract promises it is audited and there is no audit
service yet, so the route is held until audit exists or the contract owner approves a documented change.
There is also no operator route to unstick queued or sending messages; recovery is internal (recover_stuck)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from eos_core.db import get_db
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import messages, preferences, templates
from ..application.common import canonical_uuid
from ..domain.errors import NotificationError
from . import schemas
from .schemas import Channel, NewMessageIn, NewTemplateIn, PreferencesIn, PreviewIn, PublicStatus

router = APIRouter(tags=["notification"])


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except NotificationError as e:
        raise HTTPException(e.status, e.detail) from e


@router.post("/messages", status_code=202)
def send_message(
    body: NewMessageIn,
    response: Response,
    p: Principal = Depends(require("notification:message:send")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        message, created = messages.send_message(
            db,
            template=body.template,
            recipient=body.recipient.model_dump(),
            channel=body.channel,
            category=body.category,
            variables=body.variables,
            client_token=body.client_token,
            attachments=body.attachments,
            send_after=body.send_after,
        )
    if not created:
        response.status_code = 200  # the original, not a second send
    return schemas.message_out(message)


@router.get("/messages")
def list_messages(
    recipient_id: str | None = None,
    template: str | None = None,
    channel: Channel | None = None,
    status: PublicStatus | None = None,
    sent_from: datetime | None = None,
    sent_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require("notification:message:read")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        rows, total = messages.list_messages(
            db,
            recipient_id=recipient_id,
            template=template,
            channel=channel,
            statuses=schemas.status_filter(status),
            sent_from=sent_from,
            sent_to=sent_to,
            limit=limit,
            offset=offset,
        )
    return {"items": [schemas.message_out(m) for m in rows], "total": total}


@router.get("/messages/{message_id}")
def get_message(
    message_id: str,
    p: Principal = Depends(require("notification:message:read")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return schemas.message_out(messages.get_message(db, message_id))


@router.get("/templates")
def list_templates(
    channel: Channel | None = None,
    locale: str | None = None,
    p: Principal = Depends(require("notification:template:read")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return templates.list_templates(db, channel, locale)


@router.post("/templates", status_code=201)
def upsert_template(
    body: NewTemplateIn,
    p: Principal = Depends(require("notification:template:write")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return templates.upsert_template(
            db,
            key=body.key,
            channel=body.channel,
            locale=body.locale,
            body=body.body,
            subject=body.subject,
            category=body.category,
            variables=body.variables,
        )


@router.post("/templates/{key}/preview")
def preview_template(
    key: str,
    body: PreviewIn,
    p: Principal = Depends(require("notification:template:read")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return templates.preview(db, key=key, variables=body.variables, channel=body.channel, locale=body.locale)


def _own_or_manage(user_id: str, p: Principal) -> str:
    """A person may always read and change their own preferences; anyone else needs preference:manage. The id is
    compared in canonical form, so an upper-case or braced spelling of one's own id is still one's own."""
    with _http_errors():
        uid = canonical_uuid(user_id, "user_id") or ""
    if uid != p.user_id and not p.can("notification:preference:manage"):
        raise HTTPException(403, "requires notification:preference:manage")
    return uid


# The four own-resource routes name a catalogue key like every other route, so the host's route-coverage check
# sees them guarded. \`member\` grants both self keys to every organisation user (contracts/permissions.yaml), and
# organisation=True keeps the old guarantee that a caller outside any organisation is refused.
SELF_READ = require("notification:self:read", organisation=True)
SELF_MANAGE = require("notification:self:manage", organisation=True)


@router.get("/preferences/{user_id}")
def get_preferences(user_id: str, p: Principal = Depends(SELF_READ), db: Session = Depends(get_db)):
    uid = _own_or_manage(user_id, p)
    with _http_errors():
        return preferences.get_preferences(db, uid)


@router.put("/preferences/{user_id}")
def set_preferences(
    user_id: str,
    body: PreferencesIn,
    p: Principal = Depends(SELF_MANAGE),
    db: Session = Depends(get_db),
):
    uid = _own_or_manage(user_id, p)
    with _http_errors():
        return preferences.set_preferences(
            db,
            uid,
            channels=body.channels,
            locale=body.locale,
            quiet_hours=body.quiet_hours.model_dump() if body.quiet_hours else None,
            actor=p.user_id,
        )


@router.get("/inbox")
def list_inbox(
    unread_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    p: Principal = Depends(SELF_READ),
    db: Session = Depends(get_db),
):
    with _http_errors():
        rows, unread = messages.list_inbox(db, p.user_id, unread_only=unread_only, limit=limit)
    return {"items": [schemas.message_out(m) for m in rows], "unread": unread}


@router.post("/inbox/{message_id}/read", status_code=204)
def mark_read(message_id: str, p: Principal = Depends(SELF_MANAGE), db: Session = Depends(get_db)):
    with _http_errors():
        messages.mark_read(db, p.user_id, message_id)
    return Response(status_code=204)
`,im=`"""HTTP surface of scheduler, following contracts/openapi.yaml. Job definitions are read-only here: they are
declared in code by the module that handles them."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal

from eos_core.db import get_db
from eos_core.tenant import platform_scope
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..application import jobs as jobs_module
from ..application import schedules
from ..infrastructure.config import SchedulerConfig

router = APIRouter(tags=["scheduler"])

ADMIN = "platform:scheduler:admin"


class NewScheduleIn(BaseModel):
    job: str = Field(max_length=120)
    cron: str | None = Field(None, max_length=120)
    timezone: str | None = Field(None, max_length=64)
    run_at: datetime | None = None
    arguments: dict = Field(default_factory=dict)
    enabled: bool = True
    allow_overlap: bool = False
    catch_up: Literal["once", "never"] | None = None
    organisation_id: str | None = Field(None, max_length=36, description="Super admin only, for organisation jobs")


class ScheduleChangeIn(BaseModel):
    cron: str | None = Field(None, max_length=120)
    timezone: str | None = Field(None, max_length=64)
    run_at: datetime | None = None
    arguments: dict | None = None
    enabled: bool | None = None
    allow_overlap: bool | None = None
    catch_up: Literal["once", "never"] | None = None


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except schedules.SchedulerError as e:
        raise HTTPException(e.status, e.detail) from e


@contextmanager
def _scope(p: Principal) -> Iterator[schedules.Scope]:
    """The super admin works in platform scope (every organisation and platform jobs); anyone else in their own."""
    if p.super_admin and p.can(ADMIN):
        with platform_scope():
            yield schedules.Scope(None, platform=True)
        return
    if not p.organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    yield schedules.Scope(p.organisation_id)


@router.get("/jobs")
def list_jobs(
    module: str | None = None,
    scope: Literal["platform", "organisation"] | None = None,
    p: Principal = Depends(require("scheduler:job:read")),
):
    found = [j for j in jobs_module.discover().values() if (not module or j.module == module)]
    found = [j for j in found if not scope or j.scope == scope]
    return {"items": [j.out() for j in sorted(found, key=lambda j: j.key)]}


@router.get("/schedules")
def list_schedules(
    job: str | None = None,
    organisation_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require("scheduler:schedule:read")),
    db: Session = Depends(get_db),
):
    with _scope(p) as scope:
        rows, total = schedules.list_schedules(
            db, scope, job=job, organisation_id=organisation_id, limit=limit, offset=offset
        )
        return {"items": [schedules.schedule_out(s) for s in rows], "total": total}


@router.post("/schedules", status_code=201)
def create_schedule(
    body: NewScheduleIn, p: Principal = Depends(require("scheduler:schedule:write")), db: Session = Depends(get_db)
):
    with _scope(p) as scope, _http_errors():
        made = schedules.create(
            db, jobs_module.discover(), scope, SchedulerConfig.from_env(), body.model_dump(), actor=p.user_id
        )
        return schedules.schedule_out(made)


@router.get("/schedules/{schedule_id}")
def get_schedule(
    schedule_id: str, p: Principal = Depends(require("scheduler:schedule:read")), db: Session = Depends(get_db)
):
    with _scope(p) as scope, _http_errors():
        return schedules.schedule_out(schedules.get(db, scope, schedule_id))


@router.patch("/schedules/{schedule_id}")
def change_schedule(
    schedule_id: str,
    body: ScheduleChangeIn,
    p: Principal = Depends(require("scheduler:schedule:write")),
    db: Session = Depends(get_db),
):
    with _scope(p) as scope, _http_errors():
        changed = schedules.change(db, scope, schedule_id, body.model_dump(exclude_unset=True), actor=p.user_id)
        return schedules.schedule_out(changed)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: str, p: Principal = Depends(require("scheduler:schedule:write")), db: Session = Depends(get_db)
):
    with _scope(p) as scope, _http_errors():
        schedules.remove(db, scope, schedule_id, actor=p.user_id)
    return Response(status_code=204)


@router.post("/schedules/{schedule_id}/run", status_code=202)
def run_schedule_now(
    schedule_id: str, p: Principal = Depends(require("scheduler:run:trigger")), db: Session = Depends(get_db)
):
    with _scope(p) as scope, _http_errors():
        run = schedules.run_now(db, jobs_module.discover(), scope, schedule_id, actor=p.user_id)
        return schedules.run_out(run)


@router.get("/runs")
def list_runs(
    schedule_id: str | None = None,
    job: str | None = None,
    status_: Literal["running", "succeeded", "failed", "skipped"] | None = Query(None, alias="status"),
    organisation_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require("scheduler:run:read")),
    db: Session = Depends(get_db),
):
    with _scope(p) as scope:
        rows, total = schedules.list_runs(
            db,
            scope,
            schedule_id=schedule_id,
            job=job,
            status=status_,
            organisation_id=organisation_id,
            limit=limit,
            offset=offset,
        )
        return {"items": [schedules.run_out(r) for r in rows], "total": total}


@router.get("/runs/{run_id}")
def get_run(run_id: str, p: Principal = Depends(require("scheduler:run:read")), db: Session = Depends(get_db)):
    with _scope(p) as scope, _http_errors():
        return schedules.run_out(schedules.get_run(db, scope, run_id))
`,rm=`from __future__ import annotations

import json

from eos_core.db import get_db
from eos_core.settings import settings
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import TenancyError

router = APIRouter(tags=["tenancy"])


def _err(e: TenancyError):
    return HTTPException(e.status, str(e))


class AdminUser(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)


class RegistrationRequest(BaseModel):
    organisation_name: str = Field(min_length=2, max_length=200)
    slug: str
    academy_type: str
    country: str | None = None
    admin: AdminUser
    accepted_terms: bool = False


class Verify(BaseModel):
    token: str


class Toggle(BaseModel):
    enabled: bool


class StatusChange(BaseModel):
    status: str
    reason: str


class Overrides(BaseModel):
    grant_modules: list[str] = []
    revoke_modules: list[str] = []
    reason: str = ""


class PackageRequest(BaseModel):
    academy_type: str


class Approve(BaseModel):
    reason: str = ""


class Reject(BaseModel):
    reason: str = ""


class Impersonate(BaseModel):
    user_id: str
    reason: str


class DeletionRequest(BaseModel):
    reason: str = ""
    confirm_slug: str | None = None


class PurgeRequest(BaseModel):
    force: bool = False


@router.get("/academy-types")
def academy_types():
    return service.academy_types()


@router.post("/register", status_code=201)
def register(body: RegistrationRequest, db: Session = Depends(get_db)):
    try:
        org, token = service.register(
            db,
            organisation_name=body.organisation_name,
            slug=body.slug,
            academy_type=body.academy_type,
            admin=body.admin.model_dump(),
            country=body.country,
            accepted_terms=body.accepted_terms,
        )
    except TenancyError as e:
        raise _err(e) from e
    out = org.to_dict(plan="trial")
    if settings.dev_mode:
        out["verification_token"] = token  # never in production; EOS_DEV_MODE=false removes it
    return out


@router.post("/register/verify")
def verify(body: Verify, db: Session = Depends(get_db)):
    """Returns the organisation; status is pending_approval until a super admin approves the package."""
    try:
        return service.verify(db, body.token).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.get("/organisation")
def organisation(
    p: Principal = Depends(require("tenancy:organisation:read", organisation=True)), db: Session = Depends(get_db)
):
    try:
        return service.get_organisation(db, p.organisation_id).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.get("/organisation/entitlement")
def entitlement(
    p: Principal = Depends(require("tenancy:organisation:read", organisation=True)), db: Session = Depends(get_db)
):
    return service.entitlement(db, p.organisation_id)


@router.put("/organisation/modules/{module:path}")
def toggle(
    module: str,
    body: Toggle,
    p: Principal = Depends(require("tenancy:organisation:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.toggle_module(db, p.organisation_id, module, body.enabled)
    except TenancyError as e:
        raise _err(e) from e


@router.put("/organisation/academy-package")
def request_package(
    body: PackageRequest, p: Principal = Depends(require("tenancy:organisation:manage")), db: Session = Depends(get_db)
):
    try:
        return service.request_package(db, p.organisation_id, body.academy_type).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.post("/admin/organisations/{org_id}/approve")
def admin_approve(
    org_id: str,
    body: Approve,
    p: Principal = Depends(require("platform:organisations:manage")),
    db: Session = Depends(get_db),
):
    """Approve the organisation's academic package (registration or a requested change)."""
    try:
        return service.approve(db, org_id, approved_by=p.user_id, reason=body.reason).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.post("/admin/organisations/{org_id}/reject")
def admin_reject(
    org_id: str,
    body: Reject,
    p: Principal = Depends(require("platform:organisations:manage")),
    db: Session = Depends(get_db),
):
    """Reject an organisation's registration awaiting approval: it is archived and the admin is emailed the reason."""
    try:
        return service.reject(db, org_id, rejected_by=p.user_id, reason=body.reason).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.get("/admin/organisations")
def admin_list(
    status_: str | None = Query(default=None, alias="status"),
    plan: str | None = None,
    academy_type: str | None = None,
    p: Principal = Depends(require("platform:organisations:read")),
    db: Session = Depends(get_db),
):
    return service.list_organisations(db, status=status_, plan=plan, academy_type=academy_type)


@router.get("/admin/organisations/{org_id}")
def admin_get(
    org_id: str, p: Principal = Depends(require("platform:organisations:read")), db: Session = Depends(get_db)
):
    try:
        org = service.get_organisation(db, org_id)
        return {**org.to_dict(), "entitlement": service.entitlement(db, org_id)}
    except TenancyError as e:
        raise _err(e) from e


@router.put("/admin/organisations/{org_id}/status")
def admin_status(
    org_id: str,
    body: StatusChange,
    p: Principal = Depends(require("platform:organisations:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.set_status(db, org_id, body.status, body.reason).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.put("/admin/organisations/{org_id}/overrides")
def admin_overrides(
    org_id: str,
    body: Overrides,
    p: Principal = Depends(require("platform:entitlements:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.set_overrides(db, org_id, body.grant_modules, body.revoke_modules, body.reason)
    except TenancyError as e:
        raise _err(e) from e


@router.post("/admin/organisations/{org_id}/impersonate", status_code=201)
def admin_impersonate(
    org_id: str,
    body: Impersonate,
    p: Principal = Depends(require("platform:organisations:impersonate")),
    db: Session = Depends(get_db),
):
    try:
        return service.impersonate(
            db, organisation_id=org_id, user_id=body.user_id, super_admin_id=p.user_id, reason=body.reason
        )
    except TenancyError as e:
        raise _err(e) from e


@router.get("/admin/organisations/{org_id}/export")
def admin_export(
    org_id: str,
    p: Principal = Depends(require("platform:organisation:export")),
    db: Session = Depends(get_db),
):
    """Everything held about the organisation as one JSON document (DPDP data export), as a download."""
    try:
        doc = service.export_organisation(db, org_id, actor=p.user_id)
    except TenancyError as e:
        raise _err(e) from e
    filename = f"{doc['organisation']['slug']}-export-{doc['exported_at'][:10]}.json"
    return Response(
        content=json.dumps(doc, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/admin/organisations/{org_id}")
def admin_delete(
    org_id: str,
    body: DeletionRequest | None = None,
    p: Principal = Depends(require("platform:organisation:delete")),
    db: Session = Depends(get_db),
):
    """Archive the organisation and start the retention period; its rows are purged after delete_after."""
    body = body or DeletionRequest()
    try:
        return service.request_deletion(
            db, org_id, requested_by=p.user_id, reason=body.reason, confirm_slug=body.confirm_slug
        ).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.post("/admin/organisations/{org_id}/restore")
def admin_restore(
    org_id: str,
    p: Principal = Depends(require("platform:organisation:delete")),
    db: Session = Depends(get_db),
):
    """Cancel a pending deletion: the organisation gets its previous status back."""
    try:
        return service.restore_organisation(db, org_id, actor=p.user_id).to_dict()
    except TenancyError as e:
        raise _err(e) from e


@router.post("/admin/organisations/{org_id}/purge")
def admin_purge(
    org_id: str,
    body: PurgeRequest | None = None,
    p: Principal = Depends(require("platform:organisation:delete")),
    db: Session = Depends(get_db),
):
    """Delete every row of the organisation for good, once the retention period has passed (or with force)."""
    try:
        return service.purge_organisation(db, org_id, actor=p.user_id, force=bool(body and body.force))
    except TenancyError as e:
        raise _err(e) from e
`,om=Object.assign({"../../../../../platform/billing/backend/src/eos_billing/api/router.py":nm,"../../../../../platform/event-bus/backend/src/eos_event_bus/api/router.py":tm,"../../../../../platform/identity/backend/src/eos_identity/api/router.py":sm,"../../../../../platform/notification/backend/src/eos_notification/api/router.py":am,"../../../../../platform/scheduler/backend/src/eos_scheduler/api/router.py":im,"../../../../../platform/tenancy/backend/src/eos_tenancy/api/router.py":rm}),lm=n=>n.replace(/_/g," ").replace(/^\w/,t=>t.toUpperCase());function dm(n,t){return t.split(/^(?=@router\.)/m).slice(1).flatMap(i=>{var k,h,l;const a=i.match(/^@router\.(get|post|put|patch|delete)\("([^"]+)"/);if(!a)return[];const o=((k=i.match(/def\s+(\w+)\s*\(/))==null?void 0:k[1])??"",m=(l=(h=i.match(/"""\s*([^\n"]+)/))==null?void 0:h[1])==null?void 0:l.trim(),p=i.match(/require\("([^"]+)"(,\s*organisation=True)?\s*\)/),g=p==null?void 0:p[1],u=g?p!=null&&p[2]?{kind:"permission",key:g,organisation:!0}:{kind:"permission",key:g}:/require_organisation/.test(i)?{kind:"organisation"}:/current_principal/.test(i)?{kind:"signed-in"}:{kind:"public"};return[{service:n,method:a[1].toUpperCase(),path:`/api/v1/${n}${a[2]}`,summary:m??lm(o),requires:u}]})}const cm=Object.entries(om).flatMap(([n,t])=>{var i;const s=((i=n.split("/platform/")[1])==null?void 0:i.split("/")[0])??"";return dm(s,t)});function Bt(n,t){switch(n.requires.kind){case"permission":{if(n.requires.organisation&&!t.organisationId)return!1;const s=t.organisationId?Ce.member??new Set:new Set;return t.permissions.includes(n.requires.key)||s.has(n.requires.key)}case"organisation":return!!t.organisationId;default:return!0}}const mm=n=>n.kind==="permission"?n.organisation?`${n.key} (organisation user)`:n.key:n.kind==="organisation"?"organisation user":n.kind==="signed-in"?"any signed-in user":"public",pm=new Map(Object.values(an).flatMap(n=>n.map(t=>[t.key,t.description??""]))),um={GET:"bg-[#EEEEFD] text-[#4338CA]",POST:"bg-[#E7F4EC] text-[#126B3D]",PUT:"bg-[#FEF3E2] text-[#8A4F00]",PATCH:"bg-[#FEF3E2] text-[#8A4F00]",DELETE:"bg-[#FEF2F2] text-[#B91C1C]"},gm=()=>{var E,A;const{session:n}=me(),t=Se(),s=!n,i=(n==null?void 0:n.me)??{name:"Administrator",email:"admin@example.org",roles:["org-admin"],is_super_admin:!1,permissions:Qn(["org-admin"]),organisation_id:"preview"},a=i.is_super_admin?"super-admin":i.roles[0]??"org-admin",o={permissions:i.permissions,organisationId:i.organisation_id},m=i.is_super_admin?"Platform-wide: every organisation, plan and subscription. Outside every organisation.":`One organisation: ${((E=n==null?void 0:n.organisation)==null?void 0:E.name)??"the demo organisation"}${t.profile?` (${Qe(t.profile)})`:""}.`,p=cm.filter(b=>b.requires.kind!=="public"),g=p.filter(b=>Bt(b,o)),u=[...new Set(p.map(b=>b.service))],k=[...new Set(Object.values(an).flatMap(b=>b.map(_=>_.key)))].filter(b=>b.startsWith("platform:")||b.startsWith("tenancy:")||b.startsWith("billing:")).sort(),h=new Set(i.permissions),l=["included","upgrade","not-in-profile"],y=Ne.map(b=>({suite:b,counts:l.map(_=>b.modules.filter(C=>Ie(C,t)===_).length)})),v=gn[a],x=v?qe(a):[],F=new Set(Object.values(_n).flat().map(b=>b.id));return e.jsxs("div",{className:"space-y-6",children:[e.jsx(ve,{eyebrow:e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-white"}),i.name||i.email]}),title:"Role & Access",subtitle:e.jsxs(e.Fragment,{children:[re(a)," · ",m,s&&e.jsx("span",{className:"block text-xs mt-0.5",children:"Preview: sample organisation admin, no API connected"})]})}),e.jsx(xe,{stats:[{label:"Role",icon:be,value:i.is_super_admin?"Super Admin":re(a),note:a},{label:"Scope",icon:Me,value:i.is_super_admin?"Platform":"Organisation",note:i.is_super_admin?"All organisations":((A=n==null?void 0:n.organisation)==null?void 0:A.name)??"Demo"},{label:"Permission keys",icon:Pe,value:String(i.permissions.length),note:`of ${k.length} platform keys`},{label:"API actions allowed",icon:pn,value:String(g.length),delta:`of ${p.length}`,deltaTone:"muted",note:"identity, tenancy, billing"}]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-2 gap-6",children:[e.jsxs("section",{className:z,children:[e.jsx(K,{title:"Permission keys",subtitle:"Granted to your role in contracts/permissions.yaml"}),e.jsx("ul",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:k.map(b=>{const _=h.has(b);return e.jsxs("li",{className:"px-5 py-2.5 flex items-start gap-3 text-[11px]",children:[e.jsx("span",{className:`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 ${_?"bg-[#16834B26] text-[#126B3D]":"bg-[#F1F5F9] text-[#64748B]"}`,"aria-label":_?"granted":"not granted",children:_?e.jsx(We,{className:"w-3.5 h-3.5"}):e.jsx(ie,{className:"w-3.5 h-3.5"})}),e.jsxs("div",{className:"min-w-0",children:[e.jsx("code",{className:_?"text-[#12233F]":"text-[#64748B]",children:b}),e.jsx("p",{className:"text-[#64748B]",children:pm.get(b)})]})]},b)})})]}),e.jsxs("section",{className:z,children:[e.jsx(K,{title:"Module access",subtitle:t.entitlement?`${t.profile?Qe(t.profile):""} · ${t.planTitle} plan`:"Decided per organisation by profile and plan",action:e.jsx(X,{to:"/modules",className:"text-xs font-medium text-[var(--accent)] hover:underline pt-0.5",children:"Module Registry"})}),t.entitlement?e.jsxs("table",{className:"w-full text-xs border-t border-[#F1F5F9]",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"text-[#475569]",children:[e.jsx("th",{className:"py-2 px-5 text-left font-semibold",children:"Suite"}),l.map(b=>e.jsx("th",{className:"py-2 px-2 text-center font-semibold",children:e.jsx("span",{className:`inline-flex text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap ${Zs[b]}`,children:fn[b]})},b))]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9]",children:y.map(({suite:b,counts:_})=>e.jsxs("tr",{children:[e.jsx("td",{className:"py-2 px-5 text-[#12233F]",children:Sn(b)}),_.map((C,L)=>e.jsx("td",{className:`py-2 px-2 text-center tabular-nums ${C?"text-[#12233F] font-semibold":"text-[#94A3B8]"}`,children:C},L))]},b.id))})]}):e.jsxs("p",{className:"px-5 py-4 text-xs text-[#475569] border-t border-[#F1F5F9]",children:["A super admin is outside every organisation. Each organisation's modules are its academy profile ∩ plan, plus any overrides you grant with ",e.jsx("code",{children:"platform:entitlements:manage"}),"."]})]})]}),e.jsxs("section",{className:z,children:[e.jsx(K,{title:"API actions",subtitle:"Every platform endpoint and whether your role may call it, read from the backend routers"}),e.jsx("div",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:u.map(b=>e.jsxs("div",{className:"px-5 py-3 space-y-1.5",children:[e.jsx("div",{className:"text-[11px] font-bold uppercase tracking-wider text-[#475569]",children:b}),p.filter(_=>_.service===b).map(_=>{const C=Bt(_,o);return e.jsxs("div",{className:"flex items-center gap-3 text-[11px]",children:[e.jsx("span",{className:`w-12 text-center text-[10px] font-semibold px-1.5 py-0.5 rounded ${um[_.method]??""}`,children:_.method}),e.jsx("code",{className:`truncate ${C?"text-[#12233F]":"text-[#94A3B8]"}`,children:_.path}),e.jsx("span",{className:"hidden md:block flex-1 truncate text-[#64748B]",children:_.summary}),e.jsx("code",{className:"hidden sm:block text-[10px] text-[#64748B] whitespace-nowrap",children:mm(_.requires)}),e.jsx("span",{className:`text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${C?"bg-[#16834B26] text-[#126B3D]":"bg-[#F1F5F9] text-[#64748B]"}`,children:C?"Allowed":"Not allowed"})]},_.method+_.path)})]},b))})]}),e.jsxs("section",{className:z,children:[e.jsx(K,{title:"Your dashboard layout",subtitle:v?`platform/identity/config/dashboards/${a}.yaml`:"No layout for this role",action:v&&e.jsx(X,{to:`/dashboards?role=${a}`,className:"text-xs font-medium text-[var(--accent)] hover:underline pt-0.5",children:"Preview"})}),e.jsx("div",{className:"px-5 pb-4 flex flex-wrap gap-1.5",children:x.map(b=>e.jsxs("span",{className:"inline-flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155]",children:[e.jsx(Le,{className:"w-3 h-3 text-[#64748B]"}),b,e.jsx("span",{className:F.has(b)?"text-[#126B3D]":"text-[#94A3B8]",children:F.has(b)?"built":"widget not built yet"})]},b))})]})]})},Lt=({signedIn:n,to:t})=>{const{status:s}=me();return s==="loading"?null:s==="signed-in"===n?e.jsx(Yt,{}):e.jsx(Bn,{to:t,replace:!0})},hm=()=>e.jsx(oi,{children:e.jsx(ei,{children:e.jsxs(ai,{children:[e.jsx(Q,{element:e.jsx(Lt,{signedIn:!1,to:"/dashboard"}),children:e.jsx(Q,{path:"/login",element:e.jsx(hd,{})})}),e.jsx(Q,{element:e.jsx(Lt,{signedIn:!0,to:"/login"}),children:e.jsxs(Q,{element:e.jsx(Bd,{}),children:[e.jsx(Q,{path:"/dashboard",element:e.jsx(Tc,{})}),e.jsx(Q,{path:"/admissions",element:e.jsx(Uc,{})}),e.jsx(Q,{path:"/users",element:e.jsx(Lc,{})}),e.jsx(Q,{path:"/roles",element:e.jsx($c,{})}),e.jsx(Q,{path:"/dashboards",element:e.jsx(Xc,{})}),e.jsx(Q,{path:"/modules",element:e.jsx(Yc,{})}),e.jsx(Q,{path:"/modules/:moduleId",element:e.jsx(Qc,{})}),e.jsx(Q,{path:"/audit-logs",element:e.jsx(Gc,{})}),e.jsx(Q,{path:"/profile",element:e.jsx(em,{})}),e.jsx(Q,{path:"/access",element:e.jsx(gm,{})}),e.jsx(Q,{path:"/",element:e.jsx(Bn,{to:"/dashboard",replace:!0})}),e.jsx(Q,{path:"*",element:e.jsx(Bn,{to:"/dashboard",replace:!0})})]})})]})})});document.addEventListener("pointerdown",n=>{const t=n.target.closest("button");if(!t||t.disabled)return;const s=t.getBoundingClientRect(),i=Math.max(s.width,s.height);getComputedStyle(t).position==="static"&&(t.style.position="relative"),t.style.overflow="hidden";const a=document.createElement("span");a.className="ripple",a.style.width=a.style.height=`${i}px`,a.style.left=`${n.clientX-s.left-i/2}px`,a.style.top=`${n.clientY-s.top-i/2}px`,t.appendChild(a),a.addEventListener("animationend",()=>a.remove())});da.createRoot(document.getElementById("root")).render(e.jsx($t.StrictMode,{children:e.jsx(hm,{})}));
