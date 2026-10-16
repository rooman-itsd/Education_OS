import{r as f,j as e,a as qs,g as Hs,l as Qt,b as nt,c as Us,A as _t,p as En,d as Gs,e as Ws,f as Ys,h as zs,R as Cn,P as Mn,i as Rn,k as Ks,m as Jt,n as Qs}from"./Badge-kMNB8193.js";import{_ as Js}from"./index-DP2o49uf.js";import{_ as Xs}from"./index-BLDa2NjN.js";import{_ as Zs}from"./index-Bk2NycCz.js";import{_ as ea}from"./index-DXpBTIPY.js";import{_ as ta}from"./index-CGcjIDt-.js";import{_ as na}from"./index-Cm8Cvitv.js";import{_ as sa}from"./index-DrfVAjj6.js";import{_ as aa}from"./index-CYDgtq6C.js";import{_ as ia}from"./index-BMzxeHoK.js";import{_ as ra}from"./index-CH4H0J5L.js";import{_ as oa}from"./index-CkeNuV32.js";import{_ as la}from"./index-CAg0FU6O.js";import{_ as da}from"./index-NLgkZ1Ro.js";import{_ as ca}from"./index-D1pXMdn9.js";import{_ as ma}from"./index-DHrpiO6j.js";import{_ as pa}from"./index-CW3v0sBp.js";import{_ as ua}from"./index-11G3VY4O.js";import{_ as ha}from"./index-Di5wBbtj.js";import{_ as ga}from"./index-Dsm3YnyJ.js";import{_ as fa}from"./index-vG-bqEJY.js";import{_ as ya}from"./index-9j79eqzL.js";import{_ as xa}from"./index-AejmBxQ8.js";import{_ as ba}from"./index-CIe7p7JQ.js";import{_ as va}from"./index-B-p0JPm7.js";import{_ as wa}from"./index-W0b8TDjS.js";import{_ as ka}from"./index-DjKAWLCd.js";import{_ as ja}from"./index-CKegr9Dc.js";import{_ as Fa}from"./index-BQ3-uJjJ.js";import{_ as Na}from"./index-B3Ka8y9M.js";import{_ as _a}from"./index-CcFKeK2G.js";import{_ as Sa}from"./index-CZ-kqRCi.js";import{_ as Aa}from"./index-axyDee26.js";import{_ as Ea}from"./index-C2nph71i.js";import{_ as Ca}from"./index-DT0Vku0Y.js";import{_ as Ma}from"./index-C5Fi95pE.js";import{_ as Ra}from"./index-_SjJX4lW.js";import{_ as Pa}from"./index-IBzBRSKe.js";import{_ as Da}from"./index-Cw2V3rgK.js";import{_ as Oa}from"./index-DMqGADK_.js";import{_ as Ba}from"./index-wVFdHqiv.js";import{_ as La}from"./index-Cs_H6vz7.js";import{_ as Ta}from"./index-DLWE16_c.js";function Pn(){const t=window.location.hash.replace(/^#/,"")||"/",n=t.indexOf("?"),s=(n===-1?t:t.slice(0,n))||"/";return{pathname:s.startsWith("/")?s:`/${s}`,search:n===-1?"":t.slice(n)}}let Xt=Pn(),Zt=window.location.hash;function Ia(){return window.location.hash!==Zt&&(Zt=window.location.hash,Xt=Pn()),Xt}function $a(t){return window.addEventListener("hashchange",t),()=>window.removeEventListener("hashchange",t)}function yt(t,n=!1){const s=new URL(window.location.href);s.hash=t,n?window.history.replaceState(null,"",s):window.history.pushState(null,"",s),window.dispatchEvent(new HashChangeEvent("hashchange"))}const Dn=f.createContext(null),$e=f.createContext({params:{},outlet:null});function Va({children:t}){const n=f.useSyncExternalStore($a,Ia);return e.jsx(Dn.Provider,{value:n,children:t})}function De(){const t=f.useContext(Dn);if(!t)throw new Error("useLocation() must be used inside <BrowserRouter>");return t}function xt(){return f.useCallback((t,n)=>yt(t,n==null?void 0:n.replace),[])}function qa(){return f.useContext($e).params}function On(){const{pathname:t,search:n}=De(),s=f.useMemo(()=>new URLSearchParams(n),[n]),a=f.useCallback(i=>yt(`${t}?${new URLSearchParams(i).toString()}`),[t]);return[s,a]}function Bn(){return e.jsx(e.Fragment,{children:f.useContext($e).outlet})}function St({to:t,replace:n}){return f.useLayoutEffect(()=>yt(t,n),[t,n]),null}function U(t){return null}function Ha(t,n){if(t==="*")return{};const s=t.split("/").filter(Boolean),a=n.split("/").filter(Boolean);if(s.length!==a.length)return null;const i={};for(let o=0;o<s.length;o++){const m=s[o],p=decodeURIComponent(a[o]);if(m.startsWith(":"))i[m.slice(1)]=p;else if(m!==p)return null}return i}function Ln(t,n){for(const s of f.Children.toArray(t)){if(!f.isValidElement(s))continue;const{path:a,element:i,children:o}=s.props;if(a===void 0){const p=Ln(o,n);if(p!==void 0)return e.jsx(Ua,{element:i,outlet:p});continue}const m=Ha(a,n);if(m)return e.jsx($e.Provider,{value:{params:m,outlet:null},children:i})}}function Ua({element:t,outlet:n}){const s=f.useContext($e);return e.jsx($e.Provider,{value:{params:s.params,outlet:n},children:t})}function Ga({children:t}){const{pathname:n}=De();return e.jsx(e.Fragment,{children:Ln(t,n)??null})}function W({to:t,replace:n,onClick:s,target:a,...i}){const o=m=>{s==null||s(m),!(m.defaultPrevented||m.button!==0||a||m.metaKey||m.altKey||m.ctrlKey||m.shiftKey)&&(m.preventDefault(),yt(t,n))};return e.jsx("a",{href:`#${t}`,onClick:o,target:a,...i})}function en({className:t,...n}){const{pathname:s}=De(),a=n.to.split("?")[0],i=s===a||a!=="/"&&s.startsWith(`${a}/`),o=i?[t,"active"].filter(Boolean).join(" "):t;return e.jsx(W,{"aria-current":i?"page":void 0,className:o,...n})}const At="eos.admin.preview",Tn=f.createContext(null),tn=t=>t.me.is_super_admin||t.me.roles.includes("org-admin");function Wa(t){return t instanceof _t?t.message.includes("pending_approval")?"Your organisation's academic package is waiting for platform approval. Try again once you receive the approval email.":t.status===401?"Incorrect email or password.":t.status===422?"Enter your institutional email address.":t.message:t instanceof Error?t.message:String(t)}function Ya(){try{return sessionStorage.getItem(At)==="1"}catch{return!1}}function nn(t){try{t?sessionStorage.setItem(At,"1"):sessionStorage.removeItem(At)}catch{}}function za({children:t}){const[n,s]=f.useState("loading"),[a,i]=f.useState(!1),[o,m]=f.useState(null);f.useEffect(()=>{let u=!0;return(async()=>{if(new URLSearchParams(window.location.search).get("preview")==="1"||!await qs()){if(!u)return;i(!0),s(Ya()?"signed-in":"signed-out");return}if(!Hs()){u&&s("signed-out");return}try{const g=await Qt();if(!u)return;tn(g)?(m(g),s("signed-in")):(nt(),s("signed-out"))}catch{nt(),u&&s("signed-out")}})(),()=>{u=!1}},[]);const p=f.useCallback(async(u,v)=>{if(a){nn(!0),s("signed-in");return}await Us(u,v);const g=await Qt();if(!tn(g))throw nt(),new Error("This account is not an administrator. Sign in with a super admin or organisation admin account.");m(g),s("signed-in")},[a]),h=f.useCallback(()=>{nt(),nn(!1),m(null),s("signed-out")},[]);return e.jsx(Tn.Provider,{value:{status:n,preview:a,session:o,signIn:p,signOut:h},children:t})}function ie(){const t=f.useContext(Tn);if(!t)throw new Error("useAuth() must be used inside <AuthProvider>");return t}const Ka="/assets/academics-Ch7j_ZP9.jpg",Qa="/assets/admissions-DHoK_xvv.jpg",Ja="/assets/alumni-DwMt1H0B.jpg",Xa="/assets/assets-fnyAynY0.jpg",Za="/assets/athletes-8ToCgm8p.jpg",ei="/assets/budget-B6tm1sOF.jpg",ti="/assets/campus-mOCHWIV4.jpg",ni="/assets/e-office-iDVMvSXz.jpg",si="/assets/enrolment-BQGT5R_F.jpg",ai="/assets/eos-emblem-Cbb_MR42.png",ii="/assets/eos-logo-D5-Gnv0d.png",ri="/assets/examinations-DnnAb6ni.jpg",oi="/assets/facilities-BD_W5ucA.jpg",li="/assets/facility-booking-BWpWFtCt.jpg",di="/assets/favicon-364ohylp.png",ci="/assets/fees-GArltPur.jpg",mi="/assets/field-training-CIbir7Cz.jpg",pi="/assets/grievance-D8heymOF.jpg",ui="/assets/hostel-BwZVL_fL.jpg",hi="/assets/hr-payroll-o3oC7Mr8.jpg",gi="/assets/inventory-B1YqfEvF.jpg",fi="/assets/iqac-accreditation-QnFSqfHe.jpg",yi="/assets/library-DrZsMz4I.jpg",xi="/assets/lms-DjU532uj.jpg",bi="/assets/maintenance-RCDA5RCB.jpg",vi="/assets/nutrition-B5ZlJdOl.jpg",wi="/assets/placement-career-Bl0QnJuG.jpg",ki="/assets/portfolio-v3-BdwymtLO.jpg",ji="/assets/procurement-DFh-_lVc.jpg",Fi="/assets/productions-CbRKzsjA.jpg",Ni="/assets/projects-v2-DjSTnGW-.jpg",_i="/assets/rti-aioYs8Gz.jpg",Si="/assets/selection-process-BmyHNliD.jpg",Ai="/assets/skill-progress-nBwaRVRY.jpg",Ei="/assets/students-itOF3-0Z.jpg",Ci="/assets/timetable-Ba4peqRM.jpg",Mi="/assets/tournaments-03rqgGGp.jpg",Ri="/assets/training-C1GnZ0YI.jpg",Pi="/assets/transport-5ZqoBr-J.jpg",Di="/assets/web-portal-Bm0MxC8O.jpg",Oi=Object.assign({"../assets/academics.jpg":Ka,"../assets/admissions.jpg":Qa,"../assets/alumni.jpg":Ja,"../assets/assets.jpg":Xa,"../assets/athletes.jpg":Za,"../assets/budget.jpg":ei,"../assets/campus.jpg":ti,"../assets/e-office.jpg":ni,"../assets/enrolment.jpg":si,"../assets/eos-emblem.png":ai,"../assets/eos-logo.png":ii,"../assets/examinations.jpg":ri,"../assets/facilities.jpg":oi,"../assets/facility-booking.jpg":li,"../assets/favicon.png":di,"../assets/fees.jpg":ci,"../assets/field-training.jpg":mi,"../assets/grievance.jpg":pi,"../assets/hostel.jpg":ui,"../assets/hr-payroll.jpg":hi,"../assets/inventory.jpg":gi,"../assets/iqac-accreditation.jpg":fi,"../assets/library.jpg":yi,"../assets/lms.jpg":xi,"../assets/maintenance.jpg":bi,"../assets/nutrition.jpg":vi,"../assets/placement-career.jpg":wi,"../assets/portfolio-v3.jpg":ki,"../assets/procurement.jpg":ji,"../assets/productions.jpg":Fi,"../assets/projects-v2.jpg":Ni,"../assets/rti.jpg":_i,"../assets/selection-process.jpg":Si,"../assets/skill-progress.jpg":Ai,"../assets/students.jpg":Ei,"../assets/timetable.jpg":Ci,"../assets/tournaments.jpg":Mi,"../assets/training.jpg":Ri,"../assets/transport.jpg":Pi,"../assets/web-portal.jpg":Di});function O(t){const n=Oi[`../assets/${t.replace(/^\//,"")}`];if(!n)throw new Error(`missing admin asset: ${t}`);return n}const Bi=t=>Object.keys(t).some(n=>n.startsWith("aria-")||n==="role"||n==="title");function F(t,n){const s=f.forwardRef(({color:a,size:i,width:o,height:m,strokeWidth:p,absoluteStrokeWidth:h,className:u="",children:v,...g},l)=>{const x=o??i??24,w=m??i??24,N=h?Number(p??2)*24/Number(i??o??24):p??2,b=["lucide",`lucide-${t}`,...u.split(" ")].filter((S,E,y)=>S.trim()!==""&&y.indexOf(S)===E);return f.createElement("svg",{ref:l,xmlns:"http://www.w3.org/2000/svg",width:x,height:w,viewBox:"0 0 24 24",fill:"none",stroke:a||"currentColor",strokeWidth:N,strokeLinecap:"round",strokeLinejoin:"round",className:b.join(" "),...v||Bi(g)?{}:{"aria-hidden":"true"},...g},...n.map(([S,E],y)=>f.createElement(S,{key:y,...E})),v)});return s.displayName=t,s}const Et=F("activity",[["path",{d:"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"}]]),Ye=F("triangle-alert",[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"}],["path",{d:"M12 9v4"}],["path",{d:"M12 17h.01"}]]),Li=F("apple",[["path",{d:"M12 6.528V3a1 1 0 0 1 1-1h0"}],["path",{d:"M18.237 21A15 15 0 0 0 22 11a6 6 0 0 0-10-4.472A6 6 0 0 0 2 11a15.1 15.1 0 0 0 3.763 10 3 3 0 0 0 3.648.648 5.5 5.5 0 0 1 5.178 0A3 3 0 0 0 18.237 21"}]]),ge=F("arrow-right",[["path",{d:"M5 12h14"}],["path",{d:"m12 5 7 7-7 7"}]]),Ti=F("award",[["path",{d:"m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"}],["circle",{cx:"12",cy:"8",r:"6"}]]),Ii=F("badge-check",[["path",{d:"M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"}],["path",{d:"m16 9-5.5 5.5L8 12"}]]),In=F("bell",[["path",{d:"M10.268 21a2 2 0 0 0 3.464 0"}],["path",{d:"M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"}]]),rt=F("blocks",[["path",{d:"M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2"}],["rect",{x:"14",y:"2",width:"8",height:"8",rx:"1"}]]),$i=F("book-bookmark",[["path",{d:"M10 2v7.751a.25.25 0 00.407.195l2.28-1.834a.5.5 0 01.627 0l2.28 1.834A.25.25 0 0016 9.751V2"}],["path",{d:"M4 19.5v-15A2.5 2.5 0 016.5 2H19a1 1 0 011 1v18a1 1 0 01-1 1H6.5a1 1 0 010-5H20"}]]),Lt=F("book-open",[["path",{d:"M12 5v16"}],["path",{d:"M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z"}]]),$n=F("boxes",[["path",{d:"M2.97 12.92A2 2 0 0 0 2 14.63v3.24a2 2 0 0 0 .97 1.71l3 1.8a2 2 0 0 0 2.06 0L12 19v-5.5l-5-3-4.03 2.42Z"}],["path",{d:"m7 16.5-4.74-2.85"}],["path",{d:"m7 16.5 5-3"}],["path",{d:"M7 16.5v5.17"}],["path",{d:"M12 13.5V19l3.97 2.38a2 2 0 0 0 2.06 0l3-1.8a2 2 0 0 0 .97-1.71v-3.24a2 2 0 0 0-.97-1.71L17 10.5l-5 3Z"}],["path",{d:"m17 16.5-5-3"}],["path",{d:"m17 16.5 4.74-2.85"}],["path",{d:"M17 16.5v5.17"}],["path",{d:"M7.97 4.42A2 2 0 0 0 7 6.13v4.37l5 3 5-3V6.13a2 2 0 0 0-.97-1.71l-3-1.8a2 2 0 0 0-2.06 0l-3 1.8Z"}],["path",{d:"M12 8 7.26 5.15"}],["path",{d:"m12 8 4.74-2.85"}],["path",{d:"M12 13.5V8"}]]),Vi=F("briefcase",[["path",{d:"M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"}],["rect",{width:"20",height:"14",x:"2",y:"6",rx:"2"}]]),qi=F("building",[["path",{d:"M12 10h.01"}],["path",{d:"M12 14h.01"}],["path",{d:"M12 6h.01"}],["path",{d:"M16 10h.01"}],["path",{d:"M16 14h.01"}],["path",{d:"M16 6h.01"}],["path",{d:"M8 10h.01"}],["path",{d:"M8 14h.01"}],["path",{d:"M8 6h.01"}],["path",{d:"M9 22v-3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3"}],["rect",{x:"4",y:"2",width:"16",height:"20",rx:"2"}]]),Oe=F("building-complex",[["path",{d:"M10 12h4"}],["path",{d:"M10 8h4"}],["path",{d:"M14 21v-3a2 2 0 0 0-4 0v3"}],["path",{d:"M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2"}],["path",{d:"M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"}]]),Hi=F("bus",[["path",{d:"M8 6v6"}],["path",{d:"M15 6v6"}],["path",{d:"M2 12h19.6"}],["path",{d:"M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3"}],["circle",{cx:"7",cy:"18",r:"2"}],["path",{d:"M9 18h5"}],["circle",{cx:"16",cy:"18",r:"2"}]]),Ui=F("calendar-check-2",[["path",{d:"M 19 3 L 5 3"}],["path",{d:"M 21 13 L 21 5"}],["path",{d:"M 21 5 A2 2 0 0 0 19 3"}],["path",{d:"M 3 19 A2 2 0 0 0 5 21"}],["path",{d:"M 3 5 L 3 19"}],["path",{d:"M 5 3 A2 2 0 0 0 3 5"}],["path",{d:"m16 19 2 2 4-4"}],["path",{d:"M16 2v3"}],["path",{d:"M3 9h18"}],["path",{d:"M5 21 L12.5 21"}],["path",{d:"M8 2v3"}]]),Gi=F("calendar-range",[["rect",{x:"3",y:"3",width:"18",height:"18",rx:"2"}],["path",{d:"M16 2v3"}],["path",{d:"M3 9h18"}],["path",{d:"M8 2v3"}],["path",{d:"M17 13h-6"}],["path",{d:"M13 17H7"}],["path",{d:"M7 13h.01"}],["path",{d:"M17 17h.01"}]]),Ve=F("check",[["path",{d:"M20 6 9 17l-5-5"}]]),z=F("circle-check",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m16 9-5.5 5.5L8 12"}]]),ze=F("chevron-down",[["path",{d:"m6 9 6 6 6-6"}]]),Wi=F("chevron-left",[["path",{d:"m15 18-6-6 6-6"}]]),Vn=F("chevron-right",[["path",{d:"m9 18 6-6-6-6"}]]),Yi=F("clipboard-list",[["rect",{width:"8",height:"4",x:"8",y:"2",rx:"1",ry:"1"}],["path",{d:"M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"}],["path",{d:"M12 11h4"}],["path",{d:"M12 16h4"}],["path",{d:"M8 11h.01"}],["path",{d:"M8 16h.01"}]]),Ke=F("clock",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M12 6v6l4 2"}]]),zi=F("cpu",[["path",{d:"M12 20v2"}],["path",{d:"M12 2v2"}],["path",{d:"M17 20v2"}],["path",{d:"M17 2v2"}],["path",{d:"M2 12h2"}],["path",{d:"M2 17h2"}],["path",{d:"M2 7h2"}],["path",{d:"M20 12h2"}],["path",{d:"M20 17h2"}],["path",{d:"M20 7h2"}],["path",{d:"M7 20v2"}],["path",{d:"M7 2v2"}],["rect",{x:"4",y:"4",width:"16",height:"16",rx:"2"}],["rect",{x:"8",y:"8",width:"8",height:"8",rx:"1"}]]),Ki=F("credit-card",[["rect",{width:"20",height:"14",x:"2",y:"5",rx:"2"}],["line",{x1:"2",x2:"22",y1:"10",y2:"10"}],["path",{d:"M6 14h2"}]]),Tt=F("download",[["path",{d:"M12 15V3"}],["path",{d:"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}],["path",{d:"m7 10 5 5 5-5"}]]),Qi=F("cloud-download",[["path",{d:"M12 13v8l-4-4"}],["path",{d:"m12 21 4-4"}],["path",{d:"M4.393 15.269A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.436 8.284"}]]),Ji=F("dumbbell",[["path",{d:"M17.596 12.768a2 2 0 1 0 2.829-2.829l-1.768-1.767a2 2 0 0 0 2.828-2.829l-2.828-2.828a2 2 0 0 0-2.829 2.828l-1.767-1.768a2 2 0 1 0-2.829 2.829z"}],["path",{d:"m2.5 21.5 1.4-1.4"}],["path",{d:"m20.1 3.9 1.4-1.4"}],["path",{d:"M5.343 21.485a2 2 0 1 0 2.829-2.828l1.767 1.768a2 2 0 1 0 2.829-2.829l-6.364-6.364a2 2 0 1 0-2.829 2.829l1.768 1.767a2 2 0 0 0-2.828 2.829z"}],["path",{d:"m9.6 14.4 4.8-4.8"}]]),Xi=F("eye-off",[["path",{d:"M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"}],["path",{d:"M14.084 14.158a3 3 0 0 1-4.242-4.242"}],["path",{d:"M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"}],["path",{d:"m2 2 20 20"}]]),Qe=F("file-check-corner",[["path",{d:"M10.5 22H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v6"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"m14 20 2 2 4-4"}]]),sn=F("file-clock",[["path",{d:"M16 22h2a2 2 0 0 0 2-2V8a2.4 2.4 0 0 0-.706-1.706l-3.588-3.588A2.4 2.4 0 0 0 14 2H6a2 2 0 0 0-2 2v2.85"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"M8 14v2.2l1.6 1"}],["circle",{cx:"8",cy:"16",r:"6"}]]),ot=F("file-code-corner",[["path",{d:"M4 12.15V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2h-3.35"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"m5 16-3 3 3 3"}],["path",{d:"m9 22 3-3-3-3"}]]),Zi=F("file-text",[["path",{d:"M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"M10 9H8"}],["path",{d:"M16 13H8"}],["path",{d:"M16 17H8"}]]),er=F("folder-open",[["path",{d:"m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"}]]),tr=F("globe",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"}],["path",{d:"M2 12h20"}]]),qe=F("graduation-cap",[["path",{d:"M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"}],["path",{d:"M22 10v6"}],["path",{d:"M6 12.5V16a6 3 0 0 0 12 0v-3.5"}]]),Ct=F("hammer",[["path",{d:"m15 12-9.373 9.373a1 1 0 0 1-3.001-3L12 9"}],["path",{d:"m18 15 4-4"}],["path",{d:"m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172v-.344a2 2 0 0 0-.586-1.414l-1.657-1.657A6 6 0 0 0 12.516 3H9l1.243 1.243A6 6 0 0 1 12 8.485V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5"}]]),nr=F("handshake",[["path",{d:"m11 17 2 2a1 1 0 1 0 3-3"}],["path",{d:"m14 14 2.5 2.5a1 1 0 1 0 3-3l-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4"}],["path",{d:"m21 3 1 11h-2"}],["path",{d:"M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3"}],["path",{d:"M3 4h8"}]]),sr=F("circle-question-mark",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"}],["path",{d:"M12 17h.01"}]]),qn=F("rotate-ccw-clock",[["path",{d:"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"}],["path",{d:"M3 3v5h5"}],["path",{d:"M12 7v5l4 2"}]]),Hn=F("house",[["path",{d:"M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"}],["path",{d:"M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"}]]),Mt=F("indian-rupee",[["path",{d:"M6 3h12"}],["path",{d:"M6 8h12"}],["path",{d:"m6 13 8.5 8"}],["path",{d:"M6 13h3"}],["path",{d:"M9 13c6.667 0 6.667-10 0-10"}]]),Ne=F("key-round",[["path",{d:"M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"}],["circle",{cx:"16.5",cy:"7.5",r:".5",fill:"currentColor"}]]),ar=F("landmark",[["path",{d:"M10 18v-7"}],["path",{d:"M11.119 2.205a2 2 0 0 1 1.762 0l7.84 3.846A.5.5 0 0 1 20.5 7h-17a.5.5 0 0 1-.22-.949z"}],["path",{d:"M14 18v-7"}],["path",{d:"M18 18v-7"}],["path",{d:"M3 22h18"}],["path",{d:"M6 18v-7"}]]),Un=F("layers",[["path",{d:"M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"}],["path",{d:"M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"}],["path",{d:"M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"}]]),ir=F("layout-dashboard",[["rect",{width:"7",height:"9",x:"3",y:"3",rx:"1"}],["rect",{width:"7",height:"5",x:"14",y:"3",rx:"1"}],["rect",{width:"7",height:"9",x:"14",y:"12",rx:"1"}],["rect",{width:"7",height:"5",x:"3",y:"16",rx:"1"}]]),Me=F("layout-grid",[["rect",{width:"7",height:"7",x:"3",y:"3",rx:"1"}],["rect",{width:"7",height:"7",x:"14",y:"3",rx:"1"}],["rect",{width:"7",height:"7",x:"14",y:"14",rx:"1"}],["rect",{width:"7",height:"7",x:"3",y:"14",rx:"1"}]]),rr=F("library",[["path",{d:"m16 6 4 14"}],["path",{d:"M12 6v14"}],["path",{d:"M8 8v12"}],["path",{d:"M4 4v16"}]]),bt=F("life-buoy",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m4.93 4.93 4.24 4.24"}],["path",{d:"m14.83 9.17 4.24-4.24"}],["path",{d:"m14.83 14.83 4.24 4.24"}],["path",{d:"m9.17 14.83-4.24 4.24"}],["circle",{cx:"12",cy:"12",r:"4"}]]),Gn=F("lock",[["rect",{width:"18",height:"11",x:"3",y:"11",rx:"2",ry:"2"}],["path",{d:"M7 11V7a5 5 0 0 1 10 0v4"}]]),Wn=F("log-out",[["path",{d:"m16 17 5-5-5-5"}],["path",{d:"M21 12H9"}],["path",{d:"M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"}]]),or=F("medal",[["path",{d:"M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"}],["path",{d:"M11 12 5.12 2.2"}],["path",{d:"m13 12 5.88-9.8"}],["path",{d:"M8 7h8"}],["circle",{cx:"12",cy:"17",r:"5"}],["path",{d:"M12 18v-2h-.5"}]]),lr=F("megaphone",[["path",{d:"M11 6a13 13 0 0 0 8.4-2.8A1 1 0 0 1 21 4v12a1 1 0 0 1-1.6.8A13 13 0 0 0 11 14H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z"}],["path",{d:"M6 14a12 12 0 0 0 2.4 7.2 2 2 0 0 0 3.2-2.4A8 8 0 0 1 10 14"}],["path",{d:"M8 6v8"}]]),dr=F("menu",[["path",{d:"M4 5h16"}],["path",{d:"M4 12h16"}],["path",{d:"M4 19h16"}]]),cr=F("monitor-play",[["path",{d:"M15.033 9.44a.647.647 0 0 1 0 1.12l-4.065 2.352a.645.645 0 0 1-.968-.56V7.648a.645.645 0 0 1 .967-.56z"}],["path",{d:"M12 17v4"}],["path",{d:"M8 21h8"}],["rect",{x:"2",y:"3",width:"20",height:"14",rx:"2"}]]),mr=F("package",[["path",{d:"M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"}],["path",{d:"M12 22V12"}],["polyline",{points:"3.29 7 12 12 20.71 7"}],["path",{d:"m7.5 4.27 9 5.15"}]]),pr=F("chart-pie",[["path",{d:"M21 12c.552 0 1.005-.449.95-.998a10 10 0 0 0-8.953-8.951c-.55-.055-.998.398-.998.95v8a1 1 0 0 0 1 1z"}],["path",{d:"M21.21 15.89A10 10 0 1 1 8 2.83"}]]),ur=F("plug",[["path",{d:"M12 22v-5"}],["path",{d:"M15 8V2"}],["path",{d:"M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z"}],["path",{d:"M9 8V2"}]]),Yn=F("plus",[["path",{d:"M5 12h14"}],["path",{d:"M12 5v14"}]]),Rt=F("power",[["path",{d:"M12 2v10"}],["path",{d:"M18.4 6.6a9 9 0 1 1-12.77.04"}]]),hr=F("power-off",[["path",{d:"M18.36 6.64A9 9 0 0 1 20.77 15"}],["path",{d:"M6.16 6.16a9 9 0 1 0 12.68 12.68"}],["path",{d:"M12 2v4"}],["path",{d:"m2 2 20 20"}]]),zn=F("presentation",[["path",{d:"M2 3h20"}],["path",{d:"M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"}],["path",{d:"m7 21 5-5 5 5"}]]),gr=F("refresh-cw",[["path",{d:"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"}],["path",{d:"M21 3v5h-5"}],["path",{d:"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"}],["path",{d:"M8 16H3v5"}]]);F("rotate-ccw",[["path",{d:"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"}],["path",{d:"M3 3v5h5"}]]);const an=F("save",[["path",{d:"M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"}],["path",{d:"M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"}],["path",{d:"M7 3v4a1 1 0 0 0 1 1h7"}]]),It=F("scale",[["path",{d:"M12 3v18"}],["path",{d:"m19 8 3 8a5 5 0 0 1-6 0zV7"}],["path",{d:"M3 7h1a17 17 0 0 0 8-2 17 17 0 0 0 8 2h1"}],["path",{d:"m5 8 3 8a5 5 0 0 1-6 0zV7"}],["path",{d:"M7 21h10"}]]),fr=F("scroll-text",[["path",{d:"M15 12h-5"}],["path",{d:"M15 8h-5"}],["path",{d:"M19 17V5a2 2 0 0 0-2-2H4"}],["path",{d:"M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"}]]),he=F("search",[["path",{d:"m21 21-4.34-4.34"}],["circle",{cx:"11",cy:"11",r:"8"}]]),de=F("shield",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}]]),Kn=F("shield-alert",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["path",{d:"M12 8v4"}],["path",{d:"M12 16h.01"}]]),He=F("shield-check",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["path",{d:"m9 12 2 2 4-4"}]]),yr=F("shopping-bag",[["path",{d:"M16 10a4 4 0 0 1-8 0"}],["path",{d:"M3.103 6.034h17.794"}],["path",{d:"M3.4 5.467a2 2 0 0 0-.4 1.2V20a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6.667a2 2 0 0 0-.4-1.2l-2-2.667A2 2 0 0 0 17 2H7a2 2 0 0 0-1.6.8z"}]]),xr=F("siren",[["path",{d:"M7 18v-6a5 5 0 1 1 10 0v6"}],["path",{d:"M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z"}],["path",{d:"M21 12h1"}],["path",{d:"M18.5 4.5 18 5"}],["path",{d:"M2 12h1"}],["path",{d:"M12 2v1"}],["path",{d:"m4.929 4.929.707.707"}],["path",{d:"M12 12v6"}]]),br=F("timer",[["line",{x1:"10",x2:"14",y1:"2",y2:"2"}],["line",{x1:"12",x2:"15",y1:"14",y2:"11"}],["circle",{cx:"12",cy:"14",r:"8"}]]),Qn=F("trending-up",[["path",{d:"M16 7h6v6"}],["path",{d:"m22 7-8.5 8.5-5-5L2 17"}]]),Ue=F("trophy",[["path",{d:"M10 14.66V17a1 1 0 0 1-1 1 2 2 0 0 0-2 2v2"}],["path",{d:"M14 14.66V17a1 1 0 0 0 1 1 2 2 0 0 1 2 2v2"}],["path",{d:"M17.916 10H19.5A2.5 2.5 0 0 0 22 7.5V5a1 1 0 0 0-1-1h-3"}],["path",{d:"M4 22h16"}],["path",{d:"M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z"}],["path",{d:"M6.084 10H4.5A2.5 2.5 0 0 1 2 7.5V5a1 1 0 0 1 1-1h3"}]]),Jn=F("user",[["path",{d:"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"}],["circle",{cx:"12",cy:"7",r:"4"}]]),Xn=F("user-check",[["path",{d:"m16 11 2 2 4-4"}],["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}]]),vr=F("user-cog",[["path",{d:"M10 15H6a4 4 0 0 0-4 4v2"}],["path",{d:"m14.305 16.53.923-.382"}],["path",{d:"m15.228 13.852-.923-.383"}],["path",{d:"m16.852 12.228-.383-.923"}],["path",{d:"m16.852 17.772-.383.924"}],["path",{d:"m19.148 12.228.383-.923"}],["path",{d:"m19.53 18.696-.382-.924"}],["path",{d:"m20.772 13.852.924-.383"}],["path",{d:"m20.772 16.148.924.383"}],["circle",{cx:"18",cy:"15",r:"3"}],["circle",{cx:"9",cy:"7",r:"4"}]]),wr=F("user-plus",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}],["line",{x1:"19",x2:"19",y1:"8",y2:"14"}],["line",{x1:"22",x2:"16",y1:"11",y2:"11"}]]),kr=F("user-x",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}],["line",{x1:"17",x2:"22",y1:"8",y2:"13"}],["line",{x1:"22",x2:"17",y1:"8",y2:"13"}]]),Je=F("users",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["path",{d:"M16 3.128a4 4 0 0 1 0 7.744"}],["path",{d:"M22 21v-2a4 4 0 0 0-3-3.87"}],["circle",{cx:"9",cy:"7",r:"4"}]]),jr=F("users-round",[["path",{d:"M18 21a8 8 0 0 0-16 0"}],["circle",{cx:"10",cy:"8",r:"5"}],["path",{d:"M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"}]]),Fr=F("video",[["path",{d:"m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"}],["rect",{x:"2",y:"6",width:"14",height:"12",rx:"2"}]]),Zn=F("wallet",[["path",{d:"M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"}],["path",{d:"M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"}]]),Nr=F("wrench",[["path",{d:"M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z"}]]),ae=F("x",[["path",{d:"M18 6 6 18"}],["path",{d:"m6 6 12 12"}]]),es=F("circle-x",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m15 9-6 6"}],["path",{d:"m9 9 6 6"}]]),_r=F("camera",[["path",{d:"M13.997 4a2 2 0 0 1 1.76 1.05l.486.9A2 2 0 0 0 18.003 7H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1.997a2 2 0 0 0 1.759-1.048l.489-.904A2 2 0 0 1 10.004 4z"}],["circle",{cx:"12",cy:"13",r:"3"}]]),Sr=F("upload",[["path",{d:"M12 3v12"}],["path",{d:"m17 8-5-5-5 5"}],["path",{d:"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}]]),Ar=F("trash",[["path",{d:"M10 11v6"}],["path",{d:"M14 11v6"}],["path",{d:"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"}],["path",{d:"M3 6h18"}],["path",{d:"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"}]]),rn=F("pencil",[["path",{d:"M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"}],["path",{d:"m15 5 4 4"}]]),Er=F("mail",[["path",{d:"m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"}],["rect",{x:"2",y:"4",width:"20",height:"16",rx:"2"}]]);F("phone",[["path",{d:"M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"}]]);F("map-pin",[["path",{d:"M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"}],["circle",{cx:"12",cy:"10",r:"3"}]]);const Cr=F("smartphone",[["rect",{width:"14",height:"20",x:"5",y:"2",rx:"2",ry:"2"}],["path",{d:"M12 18h.01"}]]),Mr=F("languages",[["path",{d:"m5 8 6 6"}],["path",{d:"m4 14 6-6 2-3"}],["path",{d:"M2 5h12"}],["path",{d:"M7 2h1"}],["path",{d:"m22 22-5-10-5 10"}],["path",{d:"M14 18h6"}]]),Rr=F("palette",[["path",{d:"M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z"}],["circle",{cx:"13.5",cy:"6.5",r:".5",fill:"currentColor"}],["circle",{cx:"17.5",cy:"10.5",r:".5",fill:"currentColor"}],["circle",{cx:"6.5",cy:"12.5",r:".5",fill:"currentColor"}],["circle",{cx:"8.5",cy:"7.5",r:".5",fill:"currentColor"}]]);F("image",[["rect",{width:"18",height:"18",x:"3",y:"3",rx:"2",ry:"2"}],["circle",{cx:"9",cy:"9",r:"2"}],["path",{d:"m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"}]]);const Pr="font-['Montserrat','Inter',sans-serif] font-black",ts=({size:t=36})=>e.jsx("img",{src:O("/eos-emblem.png"),alt:"","aria-hidden":!0,className:"flex-shrink-0 object-contain",style:{width:t,height:t}}),ns=({className:t="text-[19px]",inverse:n=!1})=>e.jsxs("span",{className:`${Pr} uppercase leading-none tracking-[-0.02em] whitespace-nowrap ${t}`,"aria-label":"Education OS",children:[e.jsx("span",{className:n?"text-white":"text-[#001E57]",children:"Education"})," ",e.jsx("span",{className:"bg-[linear-gradient(135deg,#FD8305_0%,#FB6406_45%,#E0073F_100%)] bg-clip-text text-transparent",children:"OS"})]}),Dr=`# Module manifest — the single source of truth about this module.
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
`,Or=`# Module manifest — the single source of truth about this module.
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
`,Br=`# Module manifest — the single source of truth about this module.
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
`,Lr=`# Module manifest — the single source of truth about this module.
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
`,Tr=`# Module manifest — the single source of truth about this module.
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
`,Ir=`# Module manifest — the single source of truth about this module.
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
`,$r=`# Module manifest — the single source of truth about this module.
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
`,Vr=`# Module manifest — the single source of truth about this module.
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
`,qr=`# Module manifest — the single source of truth about this module.
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
# Proposed, pending confirmation by enrolment-registration (docs/prd.md section 8.2):
#   enrolment-registration.course-registration.confirmed
#   enrolment-registration.course-registration.withdrawn
#   enrolment-registration.section-allocation.changed
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,Hr=`# Module manifest — the single source of truth about this module.
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
`,Ur=`# Module manifest — the single source of truth about this module.
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
`,Gr=`# Module manifest — the single source of truth about this module.
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
`,Wr=`# Module manifest — the single source of truth about this module.
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
`,Yr=`# Module manifest — the single source of truth about this module.
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
`,zr=`# Module manifest — the single source of truth about this module.
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
`,Kr=`# Module manifest — the single source of truth about this module.
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
`,Qr=`# Module manifest — the single source of truth about this module.
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
`,Jr=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: asset-management
kind: feature              # feature | platform | integration
domain: facilities
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,Xr=`# Module manifest — the single source of truth about this module.
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
`,Zr=`# Module manifest — the single source of truth about this module.
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
`,eo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: maintenance
kind: feature              # feature | platform | integration
domain: facilities
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,to=`# Module manifest — the single source of truth about this module.
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
`,no=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: budget-grants
kind: feature              # feature | platform | integration
domain: finance-operations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,so=`# Module manifest — the single source of truth about this module.
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
`,ao=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: fees-accounts
kind: feature              # feature | platform | integration
domain: finance-operations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
  # Pending in the admissions contract; named in docs/architecture/ARCHITECTURE.md. Raises the admission fee invoice.
  - admissions.application.accepted

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,io=`# Module manifest — the single source of truth about this module.
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
`,ro=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: procurement
kind: feature              # feature | platform | integration
domain: finance-operations
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,oo=`# Module manifest — the single source of truth about this module.
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
`,lo=`# Module manifest — the single source of truth about this module.
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
`,co=`# Module manifest — the single source of truth about this module.
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
`,mo=`# Module manifest — the single source of truth about this module.
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
`,po=`# Module manifest — the single source of truth about this module.
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
`,uo=`# Module manifest — the single source of truth about this module.
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
`,ho=`# Module manifest — the single source of truth about this module.
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
`,go=`# Module manifest — the single source of truth about this module.
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
`,fo=`# Module manifest — the single source of truth about this module.
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
`,yo=`# Module manifest — the single source of truth about this module.
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
`,xo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: athlete-performance
kind: feature              # feature | platform | integration
domain: sports
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,bo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: sports-nutrition-health
kind: feature              # feature | platform | integration
domain: sports
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,vo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: tournament-events
kind: feature              # feature | platform | integration
domain: sports
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,wo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: training-video-analysis
kind: feature              # feature | platform | integration
domain: sports
tier: specialized   # core (platform) | common (every institution) | specialized (one field)
field: sports       # only for specialized: sports | music | arts | ...
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
consumes_events: []

# Config this module needs. Document every key in config/env.example.
config: config/env.example

# Set true only when the portability checklist in module-standard.md passes.
portable: false
`,ko=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: admissions
kind: feature              # feature | platform | integration
domain: student-lifecycle
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,jo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: enrolment-registration
kind: feature              # feature | platform | integration
domain: student-lifecycle
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
description: "Programme enrolment, semester registration, section and elective allocation."
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
`,Fo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: student-information
kind: feature              # feature | platform | integration
domain: student-lifecycle
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,No=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: web-portal-cms
kind: feature              # feature | platform | integration
domain: student-lifecycle
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,_o=`# Module manifest — the single source of truth about this module.
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
`,So=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: helpdesk
kind: feature              # feature | platform | integration
domain: support
tier: common        # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
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
`,Ao=`# Module manifest — the single source of truth about this module.
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
`,Eo=`# Module manifest — the single source of truth about this module.
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
`,Co=`# Module manifest — the single source of truth about this module.
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
`,Mo=`# Module manifest — the single source of truth about this module.
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
`,Ro=`# Module manifest — the single source of truth about this module.
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
`,Po=`# Module manifest — the single source of truth about this module.
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
`,Do=`# Module manifest — the single source of truth about this module.
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
`,Oo=`# Module manifest — the single source of truth about this module.
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
`,Bo=`# Module manifest — the single source of truth about this module.
# Read docs/architecture/module-standard.md before editing.
name: identity
kind: platform              # feature | platform | integration
domain: platform
tier: core          # core (platform) | common (every institution) | specialized (one field)
version: 0.1.0
status: planned           # planned | in-progress | stable | deprecated
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
`,Lo=`# Module manifest — the single source of truth about this module.
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
`,To=`# Module manifest — the single source of truth about this module.
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
`,Io=`# Module manifest — the single source of truth about this module.
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
`,$o=`# Module manifest — the single source of truth about this module.
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
`,Vo=`# Module manifest — the single source of truth about this module.
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
`,qo=`# Module manifest — the single source of truth about this module.
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
`,Ho=`# Module manifest — the single source of truth about this module.
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
`,Uo=`# Permission catalogue for messaging-providers. Registered with platform/identity at startup.
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

roles:
  - name: messaging-providers-operator
    description: >-
      Reads provider health when diagnosing a delivery problem. Intended for platform support,
      not for an organisation admin.
    grants:
      - messaging-providers:provider:read
`,Go=`# Permission catalogue for payment-sbiepay. Registered with platform/identity at startup.
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
`,Wo=`# Permission catalogue for academic-management. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
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
  - name: academic-management-admin
    description: Full administration of the academic catalogue. Default for org-admin.
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
  - name: academic-management-department-head
    description: Plans offerings and faculty for a department. Default for department-admin.
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
  - name: academic-management-faculty
    description: Teaches offerings and reads their rosters. Default for faculty.
    grants:
      - academic-management:term:read
      - academic-management:programme:read
      - academic-management:curriculum:read
      - academic-management:course:read
      - academic-management:offering:read
      - academic-management:faculty-assignment:read
      - academic-management:roster:read
  - name: academic-management-viewer
    description: Read-only view of the catalogue. Default for student and examination-staff.
    grants:
      - academic-management:term:read
      - academic-management:programme:read
      - academic-management:curriculum:read
      - academic-management:course:read
      - academic-management:offering:read
`,Yo=`# Permission catalogue for examinations. Registered with platform/identity at startup.
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
`,zo=`# Permission catalogue for lms. Registered with platform/identity at startup.
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
`,Ko=`# Permission catalogue for timetable-attendance. Registered with platform/identity at startup.
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
`,Qo=`# Permission catalogue for alumni. Registered with platform/identity at startup.
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
`,Jo=`# Permission catalogue for hostel. Registered with platform/identity at startup.
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
`,Xo=`# Permission catalogue for library. Registered with platform/identity at startup.
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
`,Zo=`# Permission catalogue for placement-career. Registered with platform/identity at startup.
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
`,el=`# Permission catalogue for transport. Registered with platform/identity at startup.
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
`,tl=`# Permission catalogue for asset-management. Registered with platform/identity at startup.
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
`,nl=`# Permission catalogue for facility-booking. Registered with platform/identity at startup.
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
`,sl=`# Permission catalogue for inventory-equipment. Registered with platform/identity at startup.
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
`,al=`# Permission catalogue for maintenance. Registered with platform/identity at startup.
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
`,il=`# Permission catalogue for sports-facilities. Registered with platform/identity at startup.
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
`,rl=`# Permission catalogue for budget-grants. Registered with platform/identity at startup.
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
    grants: [budget-grants:budget:read, budget-grants:budget:approve, budget-grants:grant:read, budget-grants:utilisation:approve, budget-grants:report:read]
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
`,ol=`# Permission catalogue for e-office. Registered with platform/identity at startup.
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
`,ll=`# Permission catalogue for fees-accounts. Registered with platform/identity at startup.
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
  - name: management
    grants: [fees-accounts:fee-structure:read, fees-accounts:report:read, fees-accounts:target:manage, fees-accounts:concession:approve]
  - name: org-admin
    grants: [fees-accounts:fee-structure:read, fees-accounts:invoice:read, fees-accounts:report:read, fees-accounts:target:manage]
`,dl=`# Permission catalogue for hr-payroll. Registered with platform/identity at startup.
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
`,cl=`# Permission catalogue for procurement. Registered with platform/identity at startup.
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
    description: View and decide indents raised by others (all, or one's department).
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
`,ml=`# Permission catalogue for grievance. Registered with platform/identity at startup.
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
`,pl=`# Permission catalogue for iqac-accreditation. Registered with platform/identity at startup.
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
`,ul=`# Permission catalogue for regulatory-reports. Registered with platform/identity at startup.
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
`,hl=`# Permission catalogue for rti. Registered with platform/identity at startup.
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
`,gl=`# Permission catalogue for field-training. Registered with platform/identity at startup.
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
`,fl=`# Permission catalogue for portfolio. Registered with platform/identity at startup.
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
`,yl=`# Permission catalogue for productions. Registered with platform/identity at startup.
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
`,xl=`# Permission catalogue for projects. Registered with platform/identity at startup.
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
`,bl=`# Permission catalogue for selection-process. Registered with platform/identity at startup.
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
`,vl=`# Permission catalogue for skill-progress. Registered with platform/identity at startup.
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

`,wl=`# Permission catalogue for athlete-performance. Registered with platform/identity at startup.
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
`,kl=`# Permission catalogue for sports-nutrition-health. Registered with platform/identity at startup.
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
`,jl=`# Permission catalogue for tournament-events. Registered with platform/identity at startup.
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
`,Fl=`# Permission catalogue for training-video-analysis. Registered with platform/identity at startup.
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

`,Nl=`# Permission catalogue for admissions. Registered with platform/identity at startup.
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
roles:
  - name: admissions-reviewer
    description: Reviews documents and eligibility but does not decide offers or merit lists.
    grants: [admissions:application:read, admissions:document:verify]
  - name: admissions-staff
    description: Runs the full admissions funnel for the organisation.
    grants: [admissions:application:read, admissions:application:manage, admissions:document:verify, admissions:merit-list:manage, admissions:offer:manage]
  - name: department-admin
    description: Reviews applications and merit lists for their department's programmes.
    grants: [admissions:application:read, admissions:merit-list:manage]
  - name: org-admin
    description: Read-only visibility into the organisation's admissions activity.
    grants: [admissions:application:read]
`,_l=`# Permission catalogue for enrolment-registration. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: enrolment-registration
permissions: []
#  - key: enrolment-registration:record:read
#    description: ...
#  - key: enrolment-registration:record:write
#    description: ...
roles: []
#  - name: enrolment-registration-admin
#    grants: [enrolment-registration:record:read, enrolment-registration:record:write]
`,Sl=`# Permission catalogue for student-information. Registered with platform/identity at startup.
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
# Role-to-permission composition is profile data owned by the Architecture lead
# (platform/identity/config/profiles/*.yaml), not this file. See ADR-0004.
roles: []
`,Al=`# Permission catalogue for web-portal-cms. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
# Public read (pages, announcements, the sign-up page's own content) needs no permission key.
# Organisation sign-up itself needs no web-portal-cms permission because it is not a
# web-portal-cms endpoint — platform/tenancy's POST /register is already public by its own
# contract, unmodified here.
module: web-portal-cms
permissions:
  - key: web-portal-cms:page:manage
    description: Create, edit, publish/unpublish and delete pages.
  - key: web-portal-cms:announcement:manage
    description: Create, edit, publish/unpublish and delete announcements.
roles:
  - name: web-portal-cms-editor
    description: Organisation staff who maintain the public site.
    grants: [web-portal-cms:page:manage, web-portal-cms:announcement:manage]
  - name: org-admin
    description: Full control over their own organisation's public site.
    grants: [web-portal-cms:page:manage, web-portal-cms:announcement:manage]
`,El=`# Permission catalogue for amc-vendor-support. Registered with platform/identity at startup.
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
`,Cl=`# Permission catalogue for helpdesk. Registered with platform/identity at startup.
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
`,Ml=`# Permission catalogue for incident-management. Registered with platform/identity at startup.
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
`,Rl=`# Permission catalogue for knowledge-base. Registered with platform/identity at startup.
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
`,Pl=`# Permission catalogue for sla-management. Registered with platform/identity at startup.
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
`,Dl=`# Permission catalogue for api-gateway. Registered with platform/identity at startup.
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
`,Ol=`# Permission catalogue for audit. Registered with platform/identity at startup.
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
`,Bl=`module: billing
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
`,Ll=`# Permission catalogue for documents. Registered with platform/identity at startup.
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
`,Tl=`# Permission catalogue for event-bus. Registered with platform/identity at startup.
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
    description: View relay health, backlog and stall state
  - key: platform:event-bus:admin
    description: >-
      Super admin only. Inspect and replay events across every organisation, including
      platform-level events that belong to none.

roles:
  - name: event-bus-operator
    description: >-
      Diagnoses delivery problems inside one organisation. Intended for an organisation admin,
      not a general user; seeing an event payload means seeing the data that changed.
    grants:
      - event-bus:event:read
      - event-bus:event:replay
      - event-bus:relay:read

  - name: event-bus-viewer
    description: Read-only relay health, without access to event payloads
    grants:
      - event-bus:relay:read
`,Il=`# Permission catalogue for identity. Registered with platform/identity at startup.
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
`,$l=`# Permission catalogue for integration-hub. Registered with platform/identity at startup.
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
`,Vl=`# Permission catalogue for notification. Registered with platform/identity at startup.
# Format: <module>:<resource>:<action>
module: notification
permissions:
  - key: notification:message:send
    description: >-
      Send a notification. Held by modules through packages/sdk, not by people.
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

roles:
  - name: notification-admin
    description: >-
      Manages an academy's templates and investigates delivery problems. Intended for an
      organisation admin.
    grants:
      - notification:message:read
      - notification:message:resend
      - notification:template:read
      - notification:template:write
      - notification:preference:manage

  - name: notification-viewer
    description: Read-only delivery history, for support staff diagnosing "I never got the email"
    grants:
      - notification:message:read
      - notification:template:read
`,ql=`# Permission catalogue for reporting. Registered with platform/identity at startup.
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
`,Hl=`# Permission catalogue for scheduler. Registered with platform/identity at startup.
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

roles:
  - name: scheduler-admin
    description: >-
      Manages an academy's scheduled work. Intended for an organisation admin.
    grants:
      - scheduler:job:read
      - scheduler:schedule:read
      - scheduler:schedule:write
      - scheduler:run:read
      - scheduler:run:trigger

  - name: scheduler-viewer
    description: >-
      Read-only. For support staff answering "did the overnight job run?" without the ability
      to retime or fire anything.
    grants:
      - scheduler:job:read
      - scheduler:schedule:read
      - scheduler:run:read
`,Ul=`# Permission catalogue for search. Registered with platform/identity at startup.
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
`,Gl=`# Permission catalogue for tenancy. Registered with platform/identity at startup.
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
roles:
  - name: member
    description: Implicit. Every active organisation user holds it beside their assigned roles; it is never assigned or removed by hand.
    grants: [tenancy:organisation:read]
  - name: org-admin
    description: Organisation administrator, created at registration. Scoped to one organisation.
    grants: [tenancy:organisation:read, tenancy:organisation:manage]
  - name: super-admin
    description: Platform operator. Outside every organisation.
    grants: [platform:organisations:read, platform:organisations:manage, platform:entitlements:manage, platform:organisations:impersonate]
`,Wl=`# Permission catalogue for workflow. Registered with platform/identity at startup.
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
`,Yl=Object.assign({"../../../../../integrations/digilocker/module.yaml":Dr,"../../../../../integrations/external-university-portals/module.yaml":Or,"../../../../../integrations/government-portals/module.yaml":Br,"../../../../../integrations/messaging-providers/module.yaml":Lr,"../../../../../integrations/nad/module.yaml":Tr,"../../../../../integrations/payment-sbiepay/module.yaml":Ir,"../../../../../integrations/video-conferencing/module.yaml":$r,"../../../../../integrations/wearables/module.yaml":Vr,"../../../../../modules/academics/academic-management/module.yaml":qr,"../../../../../modules/academics/examinations/module.yaml":Hr,"../../../../../modules/academics/lms/module.yaml":Ur,"../../../../../modules/academics/timetable-attendance/module.yaml":Gr,"../../../../../modules/campus-life/alumni/module.yaml":Wr,"../../../../../modules/campus-life/hostel/module.yaml":Yr,"../../../../../modules/campus-life/library/module.yaml":zr,"../../../../../modules/campus-life/placement-career/module.yaml":Kr,"../../../../../modules/campus-life/transport/module.yaml":Qr,"../../../../../modules/facilities/asset-management/module.yaml":Jr,"../../../../../modules/facilities/facility-booking/module.yaml":Xr,"../../../../../modules/facilities/inventory-equipment/module.yaml":Zr,"../../../../../modules/facilities/maintenance/module.yaml":eo,"../../../../../modules/facilities/sports-facilities/module.yaml":to,"../../../../../modules/finance-operations/budget-grants/module.yaml":no,"../../../../../modules/finance-operations/e-office/module.yaml":so,"../../../../../modules/finance-operations/fees-accounts/module.yaml":ao,"../../../../../modules/finance-operations/hr-payroll/module.yaml":io,"../../../../../modules/finance-operations/procurement/module.yaml":ro,"../../../../../modules/governance/grievance/module.yaml":oo,"../../../../../modules/governance/iqac-accreditation/module.yaml":lo,"../../../../../modules/governance/regulatory-reports/module.yaml":co,"../../../../../modules/governance/rti/module.yaml":mo,"../../../../../modules/practice/field-training/module.yaml":po,"../../../../../modules/practice/portfolio/module.yaml":uo,"../../../../../modules/practice/productions/module.yaml":ho,"../../../../../modules/practice/projects/module.yaml":go,"../../../../../modules/practice/selection-process/module.yaml":fo,"../../../../../modules/practice/skill-progress/module.yaml":yo,"../../../../../modules/sports/athlete-performance/module.yaml":xo,"../../../../../modules/sports/sports-nutrition-health/module.yaml":bo,"../../../../../modules/sports/tournament-events/module.yaml":vo,"../../../../../modules/sports/training-video-analysis/module.yaml":wo,"../../../../../modules/student-lifecycle/admissions/module.yaml":ko,"../../../../../modules/student-lifecycle/enrolment-registration/module.yaml":jo,"../../../../../modules/student-lifecycle/student-information/module.yaml":Fo,"../../../../../modules/student-lifecycle/web-portal-cms/module.yaml":No,"../../../../../modules/support/amc-vendor-support/module.yaml":_o,"../../../../../modules/support/helpdesk/module.yaml":So,"../../../../../modules/support/incident-management/module.yaml":Ao,"../../../../../modules/support/knowledge-base/module.yaml":Eo,"../../../../../modules/support/sla-management/module.yaml":Co,"../../../../../platform/api-gateway/module.yaml":Mo,"../../../../../platform/audit/module.yaml":Ro,"../../../../../platform/billing/module.yaml":Po,"../../../../../platform/documents/module.yaml":Do,"../../../../../platform/event-bus/module.yaml":Oo,"../../../../../platform/identity/module.yaml":Bo,"../../../../../platform/integration-hub/module.yaml":Lo,"../../../../../platform/notification/module.yaml":To,"../../../../../platform/reporting/module.yaml":Io,"../../../../../platform/scheduler/module.yaml":$o,"../../../../../platform/search/module.yaml":Vo,"../../../../../platform/tenancy/module.yaml":qo,"../../../../../platform/workflow/module.yaml":Ho}),ss=Object.fromEntries(Object.entries(Yl).map(([t,n])=>[t.split("/").slice(-2,-1)[0],En(n)])),zl=Object.assign({"../../../../../integrations/messaging-providers/contracts/permissions.yaml":Uo,"../../../../../integrations/payment-sbiepay/contracts/permissions.yaml":Go,"../../../../../modules/academics/academic-management/contracts/permissions.yaml":Wo,"../../../../../modules/academics/examinations/contracts/permissions.yaml":Yo,"../../../../../modules/academics/lms/contracts/permissions.yaml":zo,"../../../../../modules/academics/timetable-attendance/contracts/permissions.yaml":Ko,"../../../../../modules/campus-life/alumni/contracts/permissions.yaml":Qo,"../../../../../modules/campus-life/hostel/contracts/permissions.yaml":Jo,"../../../../../modules/campus-life/library/contracts/permissions.yaml":Xo,"../../../../../modules/campus-life/placement-career/contracts/permissions.yaml":Zo,"../../../../../modules/campus-life/transport/contracts/permissions.yaml":el,"../../../../../modules/facilities/asset-management/contracts/permissions.yaml":tl,"../../../../../modules/facilities/facility-booking/contracts/permissions.yaml":nl,"../../../../../modules/facilities/inventory-equipment/contracts/permissions.yaml":sl,"../../../../../modules/facilities/maintenance/contracts/permissions.yaml":al,"../../../../../modules/facilities/sports-facilities/contracts/permissions.yaml":il,"../../../../../modules/finance-operations/budget-grants/contracts/permissions.yaml":rl,"../../../../../modules/finance-operations/e-office/contracts/permissions.yaml":ol,"../../../../../modules/finance-operations/fees-accounts/contracts/permissions.yaml":ll,"../../../../../modules/finance-operations/hr-payroll/contracts/permissions.yaml":dl,"../../../../../modules/finance-operations/procurement/contracts/permissions.yaml":cl,"../../../../../modules/governance/grievance/contracts/permissions.yaml":ml,"../../../../../modules/governance/iqac-accreditation/contracts/permissions.yaml":pl,"../../../../../modules/governance/regulatory-reports/contracts/permissions.yaml":ul,"../../../../../modules/governance/rti/contracts/permissions.yaml":hl,"../../../../../modules/practice/field-training/contracts/permissions.yaml":gl,"../../../../../modules/practice/portfolio/contracts/permissions.yaml":fl,"../../../../../modules/practice/productions/contracts/permissions.yaml":yl,"../../../../../modules/practice/projects/contracts/permissions.yaml":xl,"../../../../../modules/practice/selection-process/contracts/permissions.yaml":bl,"../../../../../modules/practice/skill-progress/contracts/permissions.yaml":vl,"../../../../../modules/sports/athlete-performance/contracts/permissions.yaml":wl,"../../../../../modules/sports/sports-nutrition-health/contracts/permissions.yaml":kl,"../../../../../modules/sports/tournament-events/contracts/permissions.yaml":jl,"../../../../../modules/sports/training-video-analysis/contracts/permissions.yaml":Fl,"../../../../../modules/student-lifecycle/admissions/contracts/permissions.yaml":Nl,"../../../../../modules/student-lifecycle/enrolment-registration/contracts/permissions.yaml":_l,"../../../../../modules/student-lifecycle/student-information/contracts/permissions.yaml":Sl,"../../../../../modules/student-lifecycle/web-portal-cms/contracts/permissions.yaml":Al,"../../../../../modules/support/amc-vendor-support/contracts/permissions.yaml":El,"../../../../../modules/support/helpdesk/contracts/permissions.yaml":Cl,"../../../../../modules/support/incident-management/contracts/permissions.yaml":Ml,"../../../../../modules/support/knowledge-base/contracts/permissions.yaml":Rl,"../../../../../modules/support/sla-management/contracts/permissions.yaml":Pl,"../../../../../platform/api-gateway/contracts/permissions.yaml":Dl,"../../../../../platform/audit/contracts/permissions.yaml":Ol,"../../../../../platform/billing/contracts/permissions.yaml":Bl,"../../../../../platform/documents/contracts/permissions.yaml":Ll,"../../../../../platform/event-bus/contracts/permissions.yaml":Tl,"../../../../../platform/identity/contracts/permissions.yaml":Il,"../../../../../platform/integration-hub/contracts/permissions.yaml":$l,"../../../../../platform/notification/contracts/permissions.yaml":Vl,"../../../../../platform/reporting/contracts/permissions.yaml":ql,"../../../../../platform/scheduler/contracts/permissions.yaml":Hl,"../../../../../platform/search/contracts/permissions.yaml":Ul,"../../../../../platform/tenancy/contracts/permissions.yaml":Gl,"../../../../../platform/workflow/contracts/permissions.yaml":Wl}),Xe={},je={};var An;for(const[t,n]of Object.entries(zl)){const s=t.split("/").slice(-3,-2)[0],a=En(n)??{};Xe[s]=a.permissions??[];for(const i of a.roles??[]){const o=je[An=i.name]??(je[An]=new Set);for(const m of i.grants??[])o.add(m)}}function $t(t,n=!1){const s=new Set;for(const a of t)for(const i of je[a]??[])s.add(i);if(n)for(const a of Object.values(je))for(const i of a)i.startsWith("platform:")&&s.add(i);return[...s].sort()}const Ze=Gs(),Pt=Ws(),lt=Ys();function dt(t){const n=s=>s.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");return t.title.split(" / ").find(s=>n(s)===t.profile)??t.title}const Kl="sports-college",ct=Ze[Kl],Ql=new Set(["identity","tenancy","billing"]);function Vt(t,n,s,a,i){const o=ss[t];return{id:t,name:n,kind:s,suiteId:a,description:(o==null?void 0:o.description)??"",status:(o==null?void 0:o.status)??"planned",tier:(o==null?void 0:o.tier)??"",field:o==null?void 0:o.field,implemented:Ql.has(t),route:i}}const Jl=(t,n,s,a)=>Vt(n,s,"feature",t,a),oe=(t,n,s,a,i)=>({id:t,letter:n,diagram:s,name:a,domain:t,color:"#7E22CE",modules:i.map(([o,m,p])=>Jl(t,o,m,p))}),fe=[oe("student-lifecycle","A","Suite A","Pre-Admission & Student Information",[["web-portal-cms","Web Portal & CMS"],["admissions","Admission & Application","/admissions"],["student-information","Student Information (SIS)"],["enrolment-registration","Enrolment & Registration"]]),oe("academics","B","Suite B","Academic & Learning Management",[["academic-management","Academic Management"],["lms","Learning Management (LMS)"],["examinations","Examination Management"],["timetable-attendance","Timetable & Attendance"]]),oe("practice","",void 0,"Practice",[["portfolio","Portfolio"],["projects","Projects"],["selection-process","Selection Process"],["productions","Productions"],["field-training","Field Training"],["skill-progress","Skill Progress"]]),oe("sports","C","Suite C","Sports & Athlete Performance",[["athlete-performance","Athlete Performance"],["training-video-analysis","Training & Video Analysis"],["sports-nutrition-health","Sports Nutrition & Health"],["tournament-events","Tournament & Events"]]),oe("facilities","D","Suite D","Facility & Resource Management",[["sports-facilities","Sports Facilities"],["facility-booking","Facility Booking"],["inventory-equipment","Inventory & Equipment"],["asset-management","Asset Management"],["maintenance","Maintenance"]]),oe("finance-operations","E","Suite E","Finance & Institutional Operations",[["fees-accounts","Fees & Accounts"],["budget-grants","Budget & Grants"],["procurement","Procurement"],["hr-payroll","HR & Payroll"],["e-office","E-Office & Files"]]),oe("campus-life","F","Suite F","Campus Life & Student Services",[["hostel","Hostel Management"],["transport","Transport Management"],["library","Library Management"],["placement-career","Placement & Career"],["alumni","Alumni Management"]]),oe("governance","G","Suite G","Governance, Grievance & Compliance",[["grievance","Grievance (SGRC / POSH)"],["rti","RTI Management"],["iqac-accreditation","IQAC / Accreditation"],["regulatory-reports","Regulatory Reports"]]),oe("support","•","Global","Global Support Systems",[["helpdesk","Helpdesk & Ticketing"],["sla-management","SLA Management"],["knowledge-base","Knowledge Base"],["incident-management","Incident & Problem"],["amc-vendor-support","User Support & AMC"]])],vt=t=>t.diagram?`${t.diagram} · ${t.name}`:t.name,K=(t,n,s)=>Vt(t,n,"platform","platform",s),Ce=[K("identity","Identity & Access","/users"),K("tenancy","Tenancy"),K("billing","Billing"),K("workflow","Workflow & Approvals"),K("audit","Audit Log","/audit-logs"),K("notification","Notifications"),K("documents","Documents & Media"),K("reporting","Reporting & Analytics"),K("search","Global Search"),K("scheduler","Scheduler"),K("event-bus","Event Bus"),K("integration-hub","Integration Hub"),K("api-gateway","API Gateway")],ue=(t,n)=>Vt(t,n,"integration","integrations"),Te=[ue("payment-sbiepay","SBIePay"),ue("digilocker","DigiLocker"),ue("nad","NAD"),ue("government-portals","Government Systems"),ue("messaging-providers","Email / SMS / WhatsApp"),ue("video-conferencing","Video Conferencing"),ue("wearables","Wearable Devices"),ue("external-university-portals","Other University Portals")],qt=[...fe.flatMap(t=>t.modules),...Ce,...Te],Xl=new Map(qt.map(t=>[t.id,t])),Ge=t=>Xl.get(t),wt=t=>fe.find(n=>n.id===t),Zl=t=>{const n=wt(t.suiteId);return n?`${n.domain}/${t.id}`:t.id},as=t=>{var n;return((n=wt(t.suiteId))==null?void 0:n.color)??"#7E22CE"},is=t=>t.route??`/modules/${t.id}`,ed=[{icon:Oe,title:"Multi-tenant",text:"One deployment, many organisations. Each signs in to its own data."},{icon:Un,title:"Academy profiles",text:`${Object.keys(Ze).length} academy types, each with its own suites, roles and dashboards.`},{icon:Zn,title:"Plans & entitlements",text:"Trial, standard and premium plans decide which modules are on."},{icon:Ne,title:"Permission keys",text:"Every module checks keys, never roles, and records changes to audit."}],td=[{value:Object.keys(Ze).length,label:"Academy types"},{value:fe.reduce((t,n)=>t+n.modules.length,0),label:"Feature modules"},{value:Ce.length,label:"Platform services"}],nd=()=>{const t=xt(),{preview:n,signIn:s}=ie(),[a,i]=f.useState(n?"admin@example.org":""),[o,m]=f.useState(n?"••••••••••••":""),[p,h]=f.useState(!1),[u,v]=f.useState(null),g=async l=>{l.preventDefault(),h(!0),v(null);try{await s(a.trim(),o),t("/dashboard",{replace:!0})}catch(x){v(Wa(x)),h(!1)}};return e.jsxs("div",{className:"min-h-screen bg-[#F6F8FB] grid grid-cols-1 lg:grid-cols-2",children:[e.jsxs("aside",{className:"relative hidden lg:flex flex-col justify-between overflow-hidden text-white",style:{padding:40},"aria-label":"About Education OS",children:[e.jsx("div",{className:"absolute inset-0 bg-cover",style:{backgroundImage:`url('${O("/campus.jpg")}')`,backgroundPosition:"62% 72%"},"aria-hidden":!0}),e.jsx("div",{className:"absolute inset-0",style:{backgroundImage:"var(--hero-gradient)",opacity:.9},"aria-hidden":!0}),e.jsx("div",{className:"absolute inset-0 pointer-events-none",style:{backgroundImage:"radial-gradient(rgba(255,255,255,0.18) 1px, transparent 1px)",backgroundSize:"22px 22px"},"aria-hidden":!0}),e.jsx("div",{className:"absolute rounded-full pointer-events-none",style:{width:420,height:420,right:-140,top:-120,background:"radial-gradient(circle, rgba(246,91,102,0.45), transparent 70%)"},"aria-hidden":!0}),e.jsxs("div",{className:"relative z-10 flex items-center gap-3",children:[e.jsx("span",{className:"rounded-xl bg-white flex items-center justify-center shadow-lg",style:{width:48,height:48},children:e.jsx(ts,{size:36})}),e.jsx(ns,{inverse:!0,className:"text-2xl"})]}),e.jsxs("div",{className:"relative z-10 max-w-md space-y-6 eos-nav-in",children:[e.jsxs("div",{children:[e.jsx("h1",{className:"text-[32px] leading-tight font-bold tracking-[-0.02em]",children:"One platform for every institution"}),e.jsx("p",{className:"eos-hero-sub text-[14px] mt-2",children:"Configured for the way each institution teaches, trains, manages and supports its students."})]}),e.jsx("ul",{className:"space-y-3 stagger",children:ed.map(({icon:l,title:x,text:w})=>e.jsxs("li",{className:"flex items-start gap-3",children:[e.jsx("span",{className:"w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0",style:{background:"rgba(255,255,255,0.16)"},children:e.jsx(l,{className:"w-4 h-4"})}),e.jsxs("div",{children:[e.jsx("p",{className:"text-sm font-semibold",children:x}),e.jsx("p",{className:"eos-hero-sub text-xs",children:w})]})]},x))})]}),e.jsxs("div",{className:"relative z-10 space-y-4",children:[e.jsx("div",{className:"grid grid-cols-3 gap-3",children:td.map(l=>e.jsxs("div",{className:"rounded-xl p-3",style:{background:"rgba(255,255,255,0.12)",boxShadow:"inset 0 0 0 1px rgba(255,255,255,0.22)"},children:[e.jsx("div",{className:"text-2xl font-bold tabular-nums",children:l.value}),e.jsx("div",{className:"eos-hero-sub text-[11px]",children:l.label})]},l.label))}),e.jsx("p",{className:"eos-hero-sub text-[11px]",children:"© 2026 Education OS · Multi-tenant platform for higher-education institutions"})]})]}),e.jsxs("main",{className:"relative flex flex-col justify-center py-12 px-4 sm:px-8 overflow-hidden",children:[e.jsx("div",{className:"absolute inset-0 opacity-[0.03] pointer-events-none",style:{backgroundImage:"radial-gradient(#7E22CE 1px, transparent 1px)",backgroundSize:"24px 24px"},"aria-hidden":!0}),e.jsx("div",{className:"absolute rounded-full pointer-events-none",style:{width:360,height:360,left:-160,bottom:-160,background:"radial-gradient(circle, rgba(124,58,237,0.12), transparent 70%)"},"aria-hidden":!0}),e.jsxs("div",{className:"relative z-10 w-full max-w-md mx-auto page-enter",children:[e.jsxs("div",{className:"text-center",children:[e.jsx("img",{src:O("/eos-logo.png"),alt:"Education OS — University Operating System",className:"mx-auto w-full h-auto",style:{maxWidth:260}}),e.jsx("p",{className:"mt-3 text-xs text-[#475569] font-medium uppercase tracking-wider",children:"One configurable higher-education platform"})]}),e.jsxs("div",{className:"mt-6 bg-[#FFFFFF] py-8 px-6 sm:px-10 shadow-lg rounded-xl border border-[#E2E8F0]",children:[e.jsxs("div",{className:"flex items-center justify-between pb-4 border-b border-[#E2E8F0] mb-6",children:[e.jsxs("div",{children:[e.jsx("span",{className:"text-sm font-semibold text-[#12233F]",children:"Sign In to Portal"}),e.jsx("p",{className:"text-xs text-[#475569]",children:"Super admins and organisation admins"})]}),n?e.jsxs("span",{className:"inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#F39A1926] text-[#8A4F00]",children:[e.jsx(de,{className:"w-3.5 h-3.5"}),"Preview mode"]}):e.jsxs("span",{className:"inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#16834B26] text-[#126B3D]",children:[e.jsx(He,{className:"w-3.5 h-3.5"}),"Connected to API"]})]}),e.jsxs("form",{className:"space-y-4",onSubmit:g,children:[e.jsxs("div",{children:[e.jsx("label",{className:"block text-xs font-semibold text-[#12233F] mb-1.5",children:"Institutional Email"}),e.jsxs("div",{className:"relative rounded-lg shadow-2xs",children:[e.jsx("div",{className:"absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#475569]",children:e.jsx(Jn,{className:"h-4 w-4"})}),e.jsx("input",{type:"email",required:!0,value:a,onChange:l=>i(l.target.value),placeholder:"e.g. name@your-institution.edu",className:"block w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]"})]})]}),e.jsxs("div",{children:[e.jsxs("div",{className:"flex items-center justify-between mb-1.5",children:[e.jsx("label",{className:"block text-xs font-semibold text-[#12233F]",children:"Password"}),e.jsx("a",{href:"#forgot",onClick:l=>{l.preventDefault(),alert("Password reset is not available yet. Ask your organisation admin.")},className:"text-xs font-medium text-[#7E22CE] hover:underline",children:"Forgot Password?"})]}),e.jsxs("div",{className:"relative rounded-lg shadow-2xs",children:[e.jsx("div",{className:"absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-[#475569]",children:e.jsx(Gn,{className:"h-4 w-4"})}),e.jsx("input",{type:"password",required:!0,value:o,onChange:l=>m(l.target.value),placeholder:"••••••••••••",className:"block w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]"})]})]}),u&&e.jsx("p",{role:"alert",className:"rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]",children:u}),e.jsx("div",{className:"pt-1",children:e.jsx("button",{type:"submit",disabled:p,className:"w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-xs font-semibold text-white bg-[#F65B66] hover:bg-[#E9505C] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#7E22CE] transition-all shadow-md active:scale-[0.99] disabled:opacity-70",children:p?e.jsxs("span",{className:"inline-flex items-center gap-2",children:[e.jsx("span",{className:"w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"}),"Signing in..."]}):e.jsxs(e.Fragment,{children:[e.jsx("span",{children:"Sign In to Education OS"}),e.jsx(ge,{className:"w-4 h-4"})]})})})]}),n&&e.jsxs("div",{className:"mt-6 pt-5 border-t border-[#E2E8F0]",children:[e.jsx("p",{className:"text-[11px] font-semibold text-[#475569] uppercase tracking-wider mb-2 text-center",children:"Quick Prototype Demo Logins"}),e.jsx("button",{type:"button",onClick:()=>{i("admin@example.org"),m("demo")},className:"w-full px-2 py-1.5 text-[11px] font-medium rounded-md bg-[#7E22CE26] text-[#7E22CE] hover:bg-[#7E22CE40] transition-colors text-center border border-[#9333EA]/20",children:"Preview as organisation admin (sample data)"})]}),e.jsxs("div",{className:"mt-6 flex items-center justify-center gap-2 text-[11px] text-[#475569]",children:[e.jsx(de,{className:"w-3.5 h-3.5 text-[#126B3D]"}),e.jsx("span",{children:"Each organisation sees only its own data (row-level security)"})]})]}),e.jsxs("div",{className:"mt-6 text-center text-xs text-[#475569] space-y-1 lg:hidden",children:[e.jsx("p",{children:"Education OS"}),e.jsx("p",{className:"text-[11px] text-[#64748B]",children:"Multi-tenant platform for higher-education institutions"})]})]})]})]})},rs={"web-portal-cms":tr,admissions:qe,"student-information":Je,"enrolment-registration":Yi,"academic-management":Lt,lms:cr,examinations:Qe,"timetable-attendance":Ui,"athlete-performance":Ue,"training-video-analysis":Fr,"sports-nutrition-health":Li,"tournament-events":or,"sports-facilities":Ji,"facility-booking":Gi,"inventory-equipment":$n,"asset-management":mr,maintenance:Nr,"fees-accounts":Ki,"budget-grants":pr,procurement:yr,"hr-payroll":Vi,"e-office":er,hostel:Hn,transport:Hi,library:rr,"placement-career":Oe,alumni:jr,grievance:Kn,rti:Zi,"iqac-accreditation":Ii,"regulatory-reports":fr,helpdesk:bt,"sla-management":br,"knowledge-base":$i,"incident-management":xr,"amc-vendor-support":nr},sd="trial";function ye(){const{preview:t,session:n}=ie();return f.useMemo(()=>{var s;if(n!=null&&n.entitlement)return{source:"organisation",profile:Ze[n.entitlement.academyType]??null,planTitle:((s=Pt[n.entitlement.plan])==null?void 0:s.title)??n.entitlement.plan,entitlement:n.entitlement};if(t||!n){const a=Pt[sd];return{source:"preview",profile:ct,planTitle:a.title,entitlement:zs(ct,a)}}return{source:"platform",profile:null,planTitle:null,entitlement:null}},[t,n])}function Re(t,n){var a;if(t.kind==="platform")return"platform";if(!n.entitlement||!n.profile)return"per-organisation";if(t.kind==="integration"){if(!(n.profile.integrations??[]).includes(t.id))return"not-in-profile";const i=((a=Pt[n.entitlement.plan])==null?void 0:a.integrations)??[];return i.includes("*")||i.includes(t.id)?"included":"upgrade"}const s=Zl(t);return n.entitlement.modules.has(s)?"included":n.profile.modules.includes(s)?"upgrade":"not-in-profile"}const mt={included:"Included in plan",upgrade:"Upgrade to unlock","not-in-profile":"Not in academy profile",platform:"Platform service","per-organisation":"Per organisation"},ad=(t,n)=>{const s=Re(t,n);return t.implemented&&(s==="included"||s==="platform")};function Ht(){const{preview:t,session:n}=ie(),s=ye(),a=s.profile?dt(s.profile):void 0,i=s.planTitle?`${s.planTitle} plan`:void 0;return n!=null&&n.organisation?{name:n.organisation.name,detail:[a,i].filter(Boolean).join(" · "),connected:!0}:n!=null&&n.me.is_super_admin?{name:"Education OS platform",detail:"Super admin · all organisations",connected:!0}:{name:`Demo ${a??"organisation"}`,detail:[i,"preview"].filter(Boolean).join(" · "),connected:!t}}const id={"student-lifecycle":"Student Lifecycle",academics:"Academics",practice:"Practice",sports:"Sports",facilities:"Facilities","finance-operations":"Finance & Operations","campus-life":"Campus Life",governance:"Governance",support:"Global Support"},rd={"student-lifecycle":qe,academics:Lt,practice:zn,sports:Ue,facilities:Oe,"finance-operations":Zn,"campus-life":Hn,governance:It,support:bt},od={"student-lifecycle":[["admissions","Admissions"],["student-information","Students"],["enrolment-registration","Enrolment & Registration"],["web-portal-cms","Web Portal & CMS"]],academics:[["academic-management","Academic Management"],["lms","Learning (LMS)"],["examinations","Examination"],["timetable-attendance","Attendance & Timetable"]],sports:[["athlete-performance","Athletes"],["training-video-analysis","Training & Video"],["sports-nutrition-health","Nutrition & Health"],["tournament-events","Tournaments"]],facilities:[["sports-facilities","Facilities"],["facility-booking","Bookings"],["inventory-equipment","Inventory"],["asset-management","Assets"],["maintenance","Maintenance"]],"finance-operations":[["fees-accounts","Fees & Payments"],["budget-grants","Budget & Grants"],["procurement","Procurement"],["hr-payroll","HR & Payroll"],["e-office","E-Office"]],"campus-life":[["hostel","Hostel"],["transport","Transport"],["library","Library"],["placement-career","Placement & Career"],["alumni","Alumni"]],governance:[["grievance","Grievance"],["rti","RTI"],["iqac-accreditation","IQAC / Accreditation"],["regulatory-reports","Compliance & Reports"]],support:[["helpdesk","Helpdesk"],["sla-management","SLA Management"],["knowledge-base","Knowledge Base"],["incident-management","Incidents"],["amc-vendor-support","AMC & Vendors"]]},on={},ld="bg-[#FEF2F2] text-[#B91C1C]",os={name:"Dashboard",path:"/dashboard",icon:ir,live:!0},ls=[{name:"Users",path:"/users",icon:Xn,live:!0},{name:"Roles & Permissions",path:"/roles",icon:He,live:!0},{name:"Role Dashboards",path:"/dashboards",icon:Me,live:!0},{name:"Module Registry",path:"/modules",icon:rt,live:!0},{name:"Audit Log",path:"/audit-logs",icon:qn,live:!0}],dd=t=>fe.map(n=>{const s=od[n.id]??n.modules.map(a=>[a.id,a.name]);return{id:n.id,title:`${n.letter&&n.letter!=="•"?`${n.letter} · `:""}${id[n.id]??n.name}`,icon:rd[n.id]??rt,items:s.flatMap(([a,i])=>{var m,p;const o=n.modules.find(h=>h.id===a);return o?[{name:i,path:is(o),icon:rs[o.id]??rt,badge:(m=on[o.id])==null?void 0:m.value,badgeColor:(p=on[o.id])==null?void 0:p.color,live:ad(o,t)}]:[]})}}),cd=t=>t.items.reduce((n,s)=>n+(s.badgeColor===ld&&Number(s.badge)||0),0),Dt=(t,n)=>t===n||n!=="/dashboard"&&n!=="/modules"&&t.startsWith(`${n}/`),md=(t,n)=>{const s=t.find(i=>i.items.some(o=>Dt(n,o.path)));if(s)return s.id;const a=[os,...ls].find(i=>Dt(n,i.path));return a?a.path:n.startsWith("/modules/")?"/modules":void 0},pd={"student-lifecycle":{c:"#3B82F6",t:"#EFF6FF",at:"#1D4ED8"},academics:{c:"#7C3AED",t:"#F5F3FF",at:"#6D28D9"},sports:{c:"#059669",t:"#ECFDF5",at:"#047857"},facilities:{c:"#D97706",t:"#FFFBEB",at:"#B45309"},"finance-operations":{c:"#0F9F8A",t:"#F0FDFA",at:"#0F766E"},"campus-life":{c:"#E45A8A",t:"#FFF1F5",at:"#BE185D"},governance:{c:"#C026D3",t:"#FDF4FF",at:"#A21CAF"},support:{c:"#64748B",t:"#F1F5F9",at:"#334155"}},ln={c:"#4338CA",t:"#EEF2FF",ic:"#A9B3D6",h:"#F1F5F9",at:"#4338CA"},dn=t=>({"--c":t.c,"--t":t.t,"--ic":t.ic??t.c,"--h":t.h??t.t,"--at":t.at??"#12233F"}),cn=t=>`group relative w-full flex items-center gap-2.5 px-2.5 h-[34px] rounded-lg text-left text-[13px] transition-colors duration-200 ${t?"bg-[var(--t)] text-[var(--at)] font-semibold":"text-[#12233F] font-medium hover:bg-[var(--h)]"}`,mn=t=>t?"text-[var(--c)]":"text-[var(--ic)] group-hover:text-[var(--c)] group-hover:brightness-90",pn=()=>e.jsx("span",{"aria-hidden":!0,className:"eos-bar-in absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-[var(--c)]"}),un=t=>`transition-transform duration-200 group-hover:scale-105 ${t?"eos-pop":""}`,hn=({children:t,collapsed:n})=>n?e.jsx("div",{className:"mx-3 my-3 border-t border-[#EEF2F6]"}):e.jsx("div",{className:"px-3 pt-5 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#94A3B8]",children:t}),ud=({collapsed:t,onToggleCollapse:n,mobileOpen:s,onCloseMobile:a})=>{const i=De(),o=ye(),m=Ht(),p=dd(o),h=md(p,i.pathname),[u,v]=f.useState(()=>h?{[h]:!0}:{});f.useEffect(()=>{h&&v(l=>l[h]?l:{...l,[h]:!0})},[h]);const g=l=>{const x=h===l.path,w=l.icon;return e.jsxs(en,{to:l.path,onClick:a,title:t?l.name:void 0,"aria-current":x?"page":void 0,style:dn(ln),className:`${cn(x)} ${t?"justify-center px-0":""}`,children:[x&&e.jsx(pn,{}),e.jsx(w,{className:`w-[18px] h-[18px] flex-shrink-0 ${un(x)} ${mn(x)}`}),!t&&e.jsx("span",{className:"truncate flex-1",children:l.name})]},l.path)};return e.jsxs(e.Fragment,{children:[s&&e.jsx("div",{className:"fixed inset-0 bg-black/30 backdrop-blur-xs z-40 lg:hidden",onClick:a}),e.jsxs("aside",{className:`fixed top-0 bottom-0 left-0 z-50 flex flex-col eos-sidebar-bg text-[#12233F] border-r border-[#ECE6F7] transition-all duration-300 ease-in-out
          ${t?"w-[72px]":"w-[260px]"}
          ${s?"translate-x-0":"-translate-x-full lg:translate-x-0"}
        `,children:[e.jsxs("div",{className:`mx-3 mt-3 mb-2 flex items-center rounded-xl border border-[#E6ECF5] bg-[linear-gradient(135deg,#F2F7FF_0%,#FFFFFF_55%,#F1FAF4_100%)] ${t?"flex-col gap-2 px-1.5 py-2.5":"justify-between gap-2 px-2.5 py-2.5"}`,children:[e.jsxs("div",{className:"group min-w-0 flex items-center gap-2",title:"Education OS",children:[e.jsx("span",{className:"transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:scale-105",children:e.jsx(ts,{size:38})}),!t&&e.jsx("h1",{children:e.jsx(ns,{className:"text-[17px]"})})]}),e.jsx("button",{onClick:n,className:"hidden lg:flex items-center justify-center w-7 h-7 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-white/70 transition-colors flex-shrink-0",title:t?"Expand sidebar":"Collapse sidebar",children:t?e.jsx(Vn,{className:"w-4 h-4"}):e.jsx(Wi,{className:"w-4 h-4"})})]}),e.jsxs("nav",{className:"flex-1 overflow-y-auto px-3 pb-4 eos-on-dark","aria-label":"Main",children:[e.jsx("div",{className:"pt-1",children:g(os)}),e.jsx(hn,{collapsed:t,children:"Education OS"}),e.jsx("div",{className:"space-y-0.5",children:p.map((l,x)=>{const w=h===l.id,N=!!u[l.id]&&!t,b=l.icon,S=cd(l),E=pd[l.id]??ln;return e.jsxs("div",{className:"eos-nav-in",style:{...dn(E),animationDelay:`${60+x*40}ms`},children:[e.jsxs("button",{onClick:()=>{t&&n(),v(y=>({...y,[l.id]:t?!0:!y[l.id]}))},"aria-expanded":N,"aria-current":w?"location":void 0,title:t?l.title:void 0,className:`${cn(w)} ${t?"justify-center px-0":""}`,children:[w&&e.jsx(pn,{}),e.jsx(b,{className:`w-[18px] h-[18px] flex-shrink-0 ${un(w)} ${mn(w)}`}),!t&&e.jsxs(e.Fragment,{children:[e.jsx("span",{className:"truncate flex-1",children:l.title}),!N&&S>0&&e.jsxs("span",{title:`${S} urgent`,"aria-label":`${S} urgent`,className:"relative flex w-1.5 h-1.5 flex-shrink-0",children:[e.jsx("span",{className:"absolute inline-flex h-full w-full rounded-full bg-[#DC2626] opacity-60 animate-ping"}),e.jsx("span",{className:"relative inline-flex w-1.5 h-1.5 rounded-full bg-[#DC2626]"})]}),e.jsx(ze,{className:`w-4 h-4 flex-shrink-0 transition-transform duration-300 text-[var(--c)] ${w?"opacity-100":"opacity-50 group-hover:opacity-90"} ${N?"":"-rotate-90"}`})]})]}),e.jsx("div",{className:`grid transition-[grid-template-rows,opacity] duration-300 ease-out ${N?"grid-rows-[1fr] opacity-100":"grid-rows-[0fr] opacity-0"}`,...N?{}:{inert:""},children:e.jsx("div",{className:"overflow-hidden",children:e.jsx("div",{className:"ml-[19px] pl-3 border-l border-[#E2E8F0] py-1 space-y-0.5",children:l.items.map(y=>{const k=Dt(i.pathname,y.path);return e.jsxs(en,{to:y.path,onClick:a,className:`relative flex items-center gap-2 px-2.5 h-8 rounded-md text-[13px] hover:text-[#12233F] hover:bg-[#F8FAFC] hover:translate-x-1 transition-all duration-200 ${k?"text-[#0B1730]":"text-[#475569]"}`,children:[k&&e.jsx("span",{"aria-hidden":!0,className:"absolute left-[3px] top-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-[var(--c)]"}),e.jsx("span",{className:"truncate flex-1",children:y.name}),y.badge!==void 0&&e.jsx("span",{className:`text-[10px] font-semibold min-w-[20px] text-center px-1.5 py-0.5 rounded-md flex-shrink-0 ${y.badgeColor??"bg-[#F3E8FF] text-[#7E22CE]"}`,children:y.badge})]},y.path)})})})})]},l.id)})}),e.jsx(hn,{collapsed:t,children:"Administration"}),e.jsx("div",{className:"space-y-0.5 eos-nav-in",style:{animationDelay:"420ms"},children:ls.map(g)})]}),e.jsx("div",{className:"px-4 py-3 border-t border-[#E2E8F0] eos-on-dark",children:t?e.jsx("div",{className:"flex justify-center",title:m.connected?"Connected to the API":"Preview",children:e.jsx("span",{className:`w-2 h-2 rounded-full ${m.connected?"bg-[#16834B] animate-pulse":"bg-[#94A3B8]"}`})}):e.jsxs("div",{className:"flex items-center gap-2.5",children:[e.jsx("span",{className:"flex-shrink-0 w-8 h-8 rounded-lg bg-[#EEF2FF] text-[#3730A3] flex items-center justify-center",children:e.jsx(ar,{className:"w-4 h-4"})}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsxs("div",{className:"flex items-center justify-between gap-2",children:[e.jsx("p",{className:"text-[12px] font-semibold text-[#12233F] truncate",children:m.name}),m.connected?e.jsxs("span",{className:"inline-flex items-center gap-1.5 text-[10.5px] font-medium text-[#126B3D] whitespace-nowrap",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-[#16834B] animate-pulse"}),"Connected"]}):e.jsxs("span",{className:"inline-flex items-center gap-1.5 text-[10.5px] font-medium text-[#64748B] whitespace-nowrap",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-[#94A3B8]"}),"Preview"]})]}),e.jsx("p",{className:"text-[11px] text-[#64748B] truncate",children:m.detail})]})]})})]})]})},hd=[{id:"USR-1001",name:"Dr. A. Sharma",email:"a.sharma@example.edu",role:"org-admin",department:"Central Administration",status:"Active",lastLogin:"Today, 09:40 AM",dataScope:"Institution",employeeId:"ADM-2018-001",phone:"+91 98140 23891",twoFactorEnabled:!0},{id:"USR-1002",name:"P. Singh, CA",email:"p.singh@example.edu",role:"finance-staff",department:"Finance & Accounts",status:"Active",lastLogin:"Today, 10:42 AM",dataScope:"Department",employeeId:"FIN-2019-014",phone:"+91 98722 84910",twoFactorEnabled:!0},{id:"USR-1003",name:"Dr. R. Kaur",email:"r.kaur@example.edu",role:"faculty",department:"Computer Science & AI",status:"Active",lastLogin:"Yesterday, 04:15 PM",dataScope:"Assigned Records",employeeId:"FAC-2020-045",phone:"+91 94178 30129",twoFactorEnabled:!0},{id:"USR-1004",name:"Col. Gurmeet Dhillon (Retd.)",email:"g.dhillon@example.edu",role:"department-admin",department:"Sports Science & Athletics",status:"Active",lastLogin:"Today, 10:04 AM",dataScope:"Department",employeeId:"SPT-2019-003",phone:"+91 98150 99421",twoFactorEnabled:!0},{id:"USR-1005",name:"Dr. Vikram Malhotra",email:"v.malhotra@example.edu",role:"examination-staff",department:"Controller of Examinations",status:"Active",lastLogin:"Today, 10:35 AM",dataScope:"Institution",employeeId:"EXM-2021-008",phone:"+91 98881 77312",twoFactorEnabled:!0},{id:"USR-1006",name:"Rajinder Kumar",email:"r.kumar@example.edu",role:"coach",department:"Athletics & Track",status:"Active",lastLogin:"Yesterday, 06:20 PM",dataScope:"Assigned Records",employeeId:"CCH-2022-019",phone:"+91 97790 41203",twoFactorEnabled:!1},{id:"USR-1007",name:"Manpreet Sandhu",email:"m.sandhu@example.edu",role:"department-admin",department:"Physical Education",status:"Pending",lastLogin:"04 Oct 2026, 11:10 AM",dataScope:"Department",employeeId:"DPA-2024-032",phone:"+91 98144 55928",twoFactorEnabled:!1},{id:"USR-1008",name:"Sunita Verma",email:"s.verma@example.edu",role:"support-staff",department:"Student Support Center",status:"Active",lastLogin:"Today, 08:30 AM",dataScope:"Assigned Records",employeeId:"HLP-2023-011",phone:"+91 99148 66201",twoFactorEnabled:!0},{id:"USR-1009",name:"Harbhajan Chahal",email:"h.chahal@example.gov",role:"governance",department:"State Internal Audit Bureau",status:"Suspended",lastLogin:"28 Sep 2026, 02:45 PM",dataScope:"Institution",employeeId:"EXT-2022-004",phone:"+91 98765 43210",twoFactorEnabled:!0}],gd=[{id:"ADM-1024",applicant:"Harpreet Singh",programme:"B.Tech CSE (Sports Analytics)",category:"General",status:"Under Review",submitted:"05 Oct 2026",email:"h.singh2004@gmail.com",phone:"+91 98141 88204",meritRank:42,sportsDiscipline:"Athletics (400m Sprint)",notes:"National School Games Silver Medalist. 10+2 Aggregate: 91.4%",documents:[{id:"DOC-1",name:"Aadhaar Card (UIDAI Verified)",verified:!0,type:"PDF",fileSize:"1.2 MB"},{id:"DOC-2",name:"Class 12th Senior Secondary Marks Card",verified:!0,type:"PDF",fileSize:"2.4 MB"},{id:"DOC-3",name:"Passport Size Photograph & Signature",verified:!0,type:"JPG",fileSize:"480 KB"},{id:"DOC-4",name:"National Sports Merit Certificate",verified:!1,type:"PDF",fileSize:"3.1 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"05 Oct 2026, 09:14 AM",note:"Application fee ₹1,500 settled via HDFC Gateway"},{step:"Documents Uploaded",status:"completed",timestamp:"05 Oct 2026, 09:40 AM",note:"All 4 statutory credentials uploaded"},{step:"Document Verification",status:"in-progress",timestamp:"05 Oct 2026, 02:30 PM",note:"Awaiting sports certificate validation from Dean Sports"},{step:"Counselling & Seat Allotment",status:"pending",timestamp:"Scheduled for 12 Oct 2026"},{step:"Confirmation & Registration",status:"pending",timestamp:"Pending fee deposit"}]},{id:"ADM-1025",applicant:"Simran Kaur",programme:"B.Sc Sports Science & Biomechanics",category:"OBC",status:"Shortlisted",submitted:"05 Oct 2026",email:"simran.kaur.sprt@outlook.com",phone:"+91 97792 10492",meritRank:18,sportsDiscipline:"Shooting (10m Air Rifle)",notes:"Khelo India University Games Gold medalist. State quota eligible.",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.1 MB"},{id:"DOC-2",name:"10+2 Science Board Marks Card",verified:!0,type:"PDF",fileSize:"2.8 MB"},{id:"DOC-3",name:"OBC Non-Creamy Layer Certificate",verified:!0,type:"PDF",fileSize:"1.9 MB"},{id:"DOC-4",name:"Recent Photograph",verified:!0,type:"PNG",fileSize:"650 KB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"05 Oct 2026, 08:30 AM"},{step:"Documents Uploaded",status:"completed",timestamp:"05 Oct 2026, 08:45 AM"},{step:"Document Verification",status:"completed",timestamp:"05 Oct 2026, 04:15 PM",note:"Verified by Prof. S. Dhillon"},{step:"Counselling & Seat Allotment",status:"in-progress",timestamp:"Round 1 counselling call issued"},{step:"Confirmation & Registration",status:"pending",timestamp:"Awaiting candidate acceptance"}]},{id:"ADM-1026",applicant:"Arjun Sharma",programme:"BBA Sports Management",category:"General",status:"Confirmed",submitted:"04 Oct 2026",email:"arjun.sharma.mgt@yahoo.in",phone:"+91 98884 55301",meritRank:5,sportsDiscipline:"Cricket (State U-19)",notes:"Seat confirmed in Merit List 1. Semester tuition fee received in full.",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.0 MB"},{id:"DOC-2",name:"Class 12th Commerce Board Certificate",verified:!0,type:"PDF",fileSize:"3.0 MB"},{id:"DOC-3",name:"Photograph & Specimen Signature",verified:!0,type:"JPG",fileSize:"520 KB"},{id:"DOC-4",name:"Migration Certificate",verified:!0,type:"PDF",fileSize:"1.4 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"04 Oct 2026, 11:20 AM"},{step:"Documents Uploaded",status:"completed",timestamp:"04 Oct 2026, 11:40 AM"},{step:"Document Verification",status:"completed",timestamp:"04 Oct 2026, 03:00 PM"},{step:"Counselling & Seat Allotment",status:"completed",timestamp:"05 Oct 2026, 10:00 AM"},{step:"Confirmation & Registration",status:"completed",timestamp:"05 Oct 2026, 02:40 PM",note:"Fee receipt REC-99214 generated"}]},{id:"ADM-1027",applicant:"Navneet Sandhu",programme:"M.P.Ed (Physical Education)",category:"Sports Quota",status:"Under Review",submitted:"03 Oct 2026",email:"n.sandhu.track@gmail.com",phone:"+91 94170 82910",meritRank:12,sportsDiscipline:"Wrestling (Freestyle 74kg)",notes:"All India Inter-University Bronze Medalist.",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.3 MB"},{id:"DOC-2",name:"B.P.Ed Degree Transcript",verified:!0,type:"PDF",fileSize:"4.2 MB"},{id:"DOC-3",name:"Sports Performance Affidavit",verified:!1,type:"PDF",fileSize:"1.8 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"03 Oct 2026, 02:15 PM"},{step:"Documents Uploaded",status:"completed",timestamp:"03 Oct 2026, 02:35 PM"},{step:"Document Verification",status:"in-progress",timestamp:"Pending trial fitness certificate"},{step:"Counselling & Seat Allotment",status:"pending",timestamp:"Pending"},{step:"Confirmation & Registration",status:"pending",timestamp:"Pending"}]},{id:"ADM-1028",applicant:"Bhavna Rathore",programme:"B.Sc Sports Science & Biomechanics",category:"Defence",status:"Shortlisted",submitted:"03 Oct 2026",email:"bhavna.r.defence@gmail.com",phone:"+91 99150 49182",meritRank:24,sportsDiscipline:"Swimming (200m Breaststroke)",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.0 MB"},{id:"DOC-2",name:"Class 12th Marks Sheet",verified:!0,type:"PDF",fileSize:"2.5 MB"},{id:"DOC-3",name:"Priority V Defence Personnel Ward Certificate",verified:!0,type:"PDF",fileSize:"1.5 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"03 Oct 2026, 10:05 AM"},{step:"Documents Uploaded",status:"completed",timestamp:"03 Oct 2026, 10:25 AM"},{step:"Document Verification",status:"completed",timestamp:"04 Oct 2026, 11:30 AM"},{step:"Counselling & Seat Allotment",status:"in-progress",timestamp:"Allotted Priority 1 seat"},{step:"Confirmation & Registration",status:"pending",timestamp:"Pending"}]},{id:"ADM-1029",applicant:"Taranjeet Singh",programme:"B.Tech CSE (Sports Analytics)",category:"SC/ST",status:"Confirmed",submitted:"02 Oct 2026",email:"t.singh.tech@example.gov",phone:"+91 98155 33019",meritRank:8,sportsDiscipline:"Badminton",documents:[{id:"DOC-1",name:"Aadhaar Card",verified:!0,type:"PDF",fileSize:"1.1 MB"},{id:"DOC-2",name:"Class 12th Non-Medical Transcript",verified:!0,type:"PDF",fileSize:"2.1 MB"},{id:"DOC-3",name:"SC Certificate issued by Tehsildar",verified:!0,type:"PDF",fileSize:"1.4 MB"}],timeline:[{step:"Application Submitted",status:"completed",timestamp:"02 Oct 2026, 04:00 PM"},{step:"Documents Uploaded",status:"completed",timestamp:"02 Oct 2026, 04:20 PM"},{step:"Document Verification",status:"completed",timestamp:"03 Oct 2026, 11:00 AM"},{step:"Counselling & Seat Allotment",status:"completed",timestamp:"04 Oct 2026, 09:30 AM"},{step:"Confirmation & Registration",status:"completed",timestamp:"04 Oct 2026, 03:00 PM"}]}],gn=[{id:"ALT-01",title:"RTI deadline approaching",subtitle:"3 applications require immediate statutory PIO response within 48h",category:"Compliance",severity:"critical",timestamp:"10 mins ago"},{id:"ALT-02",title:"Inventory below reorder level",subtitle:"5 items in Sports Physiotherapy Clinic require restocking PO",category:"Inventory",severity:"warning",timestamp:"35 mins ago"},{id:"ALT-03",title:"Grievance case pending",subtitle:"2 student grievance tickets escalated to Proctorial Committee",category:"Grievance",severity:"warning",timestamp:"1 hour ago"},{id:"ALT-04",title:"Payment reconciliation completed",subtitle:"SBI e-Pay portal reconciled ₹1.28 Cr admission receipts for Batch 2026",category:"Finance",severity:"success",timestamp:"2 hours ago"},{id:"ALT-05",title:"System backup completed successfully",subtitle:"Daily snapshot of Oracle ERP Database archived to Disaster Recovery node",category:"System",severity:"info",timestamp:"03:00 AM"}],ds=[{id:"AUD-901",timestamp:"10:42 AM",user:"Demo organisation admin",role:"org-admin",action:"tenancy.organisation.registered",resource:"org: demo-sports-college",status:"Success",ipAddress:"172.16.2.45"},{id:"AUD-902",timestamp:"10:44 AM",user:"System",role:"system",action:"billing.subscription.started",resource:"plan: trial",status:"Success",ipAddress:"127.0.0.1"},{id:"AUD-903",timestamp:"10:51 AM",user:"Demo organisation admin",role:"org-admin",action:"tenancy.organisation.verified",resource:"org: demo-sports-college",status:"Success",ipAddress:"172.16.2.45"},{id:"AUD-904",timestamp:"10:51 AM",user:"System",role:"system",action:"tenancy.package.requested",resource:"kind: registration",status:"Warning",ipAddress:"127.0.0.1"},{id:"AUD-905",timestamp:"11:20 AM",user:"Platform operator",role:"super-admin",action:"tenancy.organisation.approved",resource:"org: demo-sports-college",status:"Success",ipAddress:"10.0.0.12"},{id:"AUD-906",timestamp:"11:20 AM",user:"System",role:"system",action:"tenancy.organisation.activated",resource:"org: demo-sports-college",status:"Success",ipAddress:"127.0.0.1"},{id:"AUD-907",timestamp:"11:34 AM",user:"Demo organisation admin",role:"org-admin",action:"identity.user.created",resource:"role: faculty",status:"Success",ipAddress:"172.16.2.45"},{id:"AUD-908",timestamp:"11:52 AM",user:"Demo organisation admin",role:"org-admin",action:"tenancy.entitlement.changed",resource:"module toggled: academics/lms",status:"Success",ipAddress:"172.16.2.45"},{id:"AUD-909",timestamp:"Yesterday, 05:22 PM",user:"Platform operator",role:"super-admin",action:"tenancy.impersonation.started",resource:"org: demo-sports-college",status:"Warning",ipAddress:"10.0.0.12"}],fd=[{year:"2023",total:2450,sportsQuota:280,academics:2170},{year:"2024",total:2910,sportsQuota:330,academics:2580},{year:"2025",total:3420,sportsQuota:395,academics:3025},{year:"2026",total:3842,sportsQuota:428,academics:3414}],cs=["#7E22CE","#4338CA","#0369A1","#15803D"],ms=[{stage:"Applications",count:1284,pct:"100%",color:"#9333EA",fill:"#9333EA"},{stage:"Shortlisted",count:824,pct:"64.2%",color:"#7E22CE",fill:"#7E22CE"},{stage:"Counselling",count:612,pct:"47.7%",color:"#16834B",fill:"#16834B"},{stage:"Confirmed",count:486,pct:"37.8%",color:"#F39A19",fill:"#F39A19"}],st={firstName:"",lastName:"",displayName:"",phone:"",jobTitle:"",bio:"",photo:null,updatedAt:null},Ot="eos-profile-change",ps=t=>`eos.admin.profile.${t}`,fn=new Map;function yd(t){let n=null;try{n=localStorage.getItem(ps(t))}catch{n=null}const s=fn.get(t);if(s&&s.raw===n)return s.value;let a=st;try{a=n?{...st,...JSON.parse(n)}:st}catch{a=st}return fn.set(t,{raw:n,value:a}),a}function xd(t,n){localStorage.setItem(ps(t),JSON.stringify({...n,updatedAt:new Date().toISOString()})),window.dispatchEvent(new Event(Ot))}function bd(t){return window.addEventListener(Ot,t),window.addEventListener("storage",t),()=>{window.removeEventListener(Ot,t),window.removeEventListener("storage",t)}}function us(t){const n=f.useSyncExternalStore(bd,()=>yd(t)),s=f.useCallback(a=>xd(t,a),[t]);return[n,s]}const vd=["image/jpeg","image/png","image/webp"],hs=2*1024*1024;async function wd(t){if(!vd.includes(t.type))throw new Error("Choose a JPG, PNG or WebP image.");if(t.size>hs)throw new Error(`The image is ${(t.size/1048576).toFixed(1)} MB; the limit is 2 MB.`);const n=URL.createObjectURL(t);try{const s=await new Promise((m,p)=>{const h=new Image;h.onload=()=>m(h),h.onerror=()=>p(new Error("This file could not be read as an image.")),h.src=n}),a=Math.min(s.naturalWidth,s.naturalHeight),i=document.createElement("canvas");i.width=i.height=256;const o=i.getContext("2d");if(!o)throw new Error("This browser cannot process images.");return o.drawImage(s,(s.naturalWidth-a)/2,(s.naturalHeight-a)/2,a,a,0,0,256,256),i.toDataURL("image/jpeg",.88)}finally{URL.revokeObjectURL(n)}}const kt=t=>t.split(/[\s@.]+/).filter(Boolean).slice(0,2).map(n=>n[0].toUpperCase()).join("")||"AD",kd=[{label:"Dashboard",hint:"dashboard",to:"/dashboard",tag:"NAV"},{label:"Users & Access",hint:"users",to:"/users",tag:"NAV"},{label:"Roles & Permissions",hint:"roles permissions keys",to:"/roles",tag:"NAV"},{label:"Role Dashboards",hint:"dashboards layouts widgets",to:"/dashboards",tag:"NAV"},{label:"Module Registry",hint:"modules entitlement",to:"/modules",tag:"NAV"},{label:"Audit Log",hint:"audit events",to:"/audit-logs",tag:"NAV"},{label:"My Profile",hint:"profile account security",to:"/profile",tag:"NAV"},{label:"Role & Access",hint:"role access permissions api",to:"/access",tag:"NAV"}],jd=({onToggleMobileMenu:t})=>{const n=De(),s=xt(),{session:a,signOut:i}=ie(),o=a==null?void 0:a.me,[m]=us((o==null?void 0:o.id)??"preview"),p=[m.firstName,m.lastName].filter(Boolean).join(" "),h=m.displayName||p||(o==null?void 0:o.name)||(o==null?void 0:o.email)||"Administrator",u=o?o.is_super_admin?"Super Admin":"Organisation Admin":"Preview",v=h.split(/[\s@.]+/).filter(Boolean).slice(0,2).map(_=>_[0].toUpperCase()).join("")||"AD",[g,l]=f.useState(""),[x,w]=f.useState(!1),[N,b]=f.useState(!1),[S,E]=f.useState(!1),[y,k]=f.useState(!1),B=g.trim().toLowerCase(),T=[...kd,...qt.map(_=>({label:_.name,hint:_.id,to:is(_),tag:_.kind==="feature"?"MOD":_.kind==="platform"?"SVC":"INT"}))].filter(_=>!B||_.label.toLowerCase().includes(B)||_.hint.includes(B)).slice(0,8),C=_=>{w(!1),l(""),s(_)},M=f.useRef(null),j=f.useRef(null);f.useEffect(()=>{const _=D=>{M.current&&!M.current.contains(D.target)&&b(!1),j.current&&!j.current.contains(D.target)&&E(!1)};return document.addEventListener("mousedown",_),()=>document.removeEventListener("mousedown",_)},[]),f.useEffect(()=>{const _=D=>{(D.metaKey||D.ctrlKey)&&D.key.toLowerCase()==="k"&&(D.preventDefault(),w(I=>!I)),D.key==="Escape"&&(w(!1),k(!1))};return window.addEventListener("keydown",_),()=>window.removeEventListener("keydown",_)},[]);const R=(()=>{var D;const _=n.pathname;if(_==="/dashboard")return[{label:"Education OS",to:"/dashboard"},{label:"Dashboard"}];if(_==="/users")return[{label:"Administration"},{label:"Users & Access"}];if(_==="/roles")return[{label:"Administration"},{label:"Roles & Permissions"}];if(_==="/admissions")return[{label:"Student Lifecycle",to:"/modules/admissions"},{label:"Admissions Workflow"}];if(_==="/audit-logs")return[{label:"Administration"},{label:"Audit Log"}];if(_==="/profile")return[{label:"Account"},{label:"My Profile"}];if(_==="/access")return[{label:"Account"},{label:"Role & Access"}];if(_==="/dashboards")return[{label:"Administration"},{label:"Role Dashboards"}];if(_==="/modules")return[{label:"Administration"},{label:"Module Registry"}];if(_.startsWith("/modules/")){const I=Ge(_.replace("/modules/",""));return[{label:(I&&((D=wt(I.suiteId))==null?void 0:D.name))??"Module Registry",to:"/modules"},{label:(I==null?void 0:I.name)??"Unknown module"}]}return[{label:"Education OS",to:"/dashboard"}]})();return e.jsxs(e.Fragment,{children:[e.jsxs("header",{className:"sticky top-0 z-30 h-16 bg-white/80 backdrop-blur-xl border-b border-[#E2E8F0] flex items-center justify-between px-4 sm:px-6",children:[e.jsxs("div",{className:"flex items-center gap-3 sm:gap-4 min-w-0",children:[e.jsx("button",{onClick:t,className:"lg:hidden p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9]","aria-label":"Open navigation menu",children:e.jsx(dr,{className:"w-5 h-5"})}),e.jsx("nav",{className:"flex items-center gap-1.5 text-xs text-[#475569] truncate",children:R.map((_,D)=>e.jsxs(Cn.Fragment,{children:[D>0&&e.jsx("span",{className:"text-[#64748B]",children:"/"}),_.to&&D<R.length-1?e.jsx(W,{to:_.to,className:"hover:text-[#7E22CE] transition-colors truncate",children:_.label}):e.jsx("span",{className:"font-semibold text-[#12233F] truncate",children:_.label})]},D))})]}),e.jsx("div",{className:"hidden md:flex items-center flex-1 max-w-md mx-6",children:e.jsxs("button",{onClick:()=>w(!0),className:"w-full flex items-center justify-between px-4 py-2 rounded-xl bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] text-xs text-[#475569] shadow-[0_4px_14px_-10px_rgba(60,80,140,0.4)] transition-colors focus:outline-none",children:[e.jsxs("div",{className:"flex items-center gap-2 truncate",children:[e.jsx(he,{className:"w-3.5 h-3.5 text-[#475569]"}),e.jsx("span",{className:"truncate",children:"Search pages and modules..."})]}),e.jsx("kbd",{className:"hidden sm:inline-flex items-center gap-0.5 text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-full bg-[#F6F8FB] text-[#475569]",children:"Ctrl K"})]})}),e.jsxs("div",{className:"flex items-center gap-2 sm:gap-3",children:[e.jsx("button",{onClick:()=>w(!0),className:"md:hidden p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9]","aria-label":"Search",children:e.jsx(he,{className:"w-4 h-4"})}),e.jsx("button",{onClick:()=>k(!0),className:"p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9] transition-colors",title:"Institutional Help & Knowledge Base",children:e.jsx(sr,{className:"w-4.5 h-4.5"})}),e.jsxs("div",{className:"relative",ref:M,children:[e.jsxs("button",{onClick:()=>b(!N),className:"relative p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9] transition-colors",title:"Notifications",children:[e.jsx(In,{className:"w-4.5 h-4.5"}),e.jsx("span",{className:"absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#DC2626] ring-2 ring-[#F6F8FB] animate-pulse"})]}),N&&e.jsxs("div",{className:"absolute right-0 mt-2 w-80 sm:w-96 rounded-xl bg-[#FFFFFF] border border-[#E2E8F0] shadow-xl py-2 z-50",children:[e.jsxs("div",{className:"flex items-center justify-between px-4 py-2 border-b border-[#E2E8F0]",children:[e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx("span",{className:"font-semibold text-xs text-[#12233F]",children:"Notifications"}),e.jsxs("span",{className:"text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#EBDCFE] text-[#6B21A8]",children:[gn.length," sample"]})]}),e.jsx("button",{onClick:()=>b(!1),className:"text-[11px] text-[#7E22CE] hover:underline font-medium",children:"Close"})]}),e.jsx("div",{className:"max-h-80 overflow-y-auto divide-y divide-[#F1F5F9]",children:gn.map(_=>e.jsxs("div",{className:"p-3 hover:bg-[#F6F8FB] transition-colors flex items-start gap-3",children:[e.jsx("div",{className:"mt-0.5",children:_.severity==="critical"?e.jsx("span",{className:"flex items-center justify-center w-6 h-6 rounded-full bg-[#DC262626] text-[#B91C1C]",children:e.jsx(Ye,{className:"w-3.5 h-3.5"})}):_.severity==="warning"?e.jsx("span",{className:"flex items-center justify-center w-6 h-6 rounded-full bg-[#FEF3E2] text-[#8A4F00]",children:e.jsx(Ke,{className:"w-3.5 h-3.5"})}):e.jsx("span",{className:"flex items-center justify-center w-6 h-6 rounded-full bg-[#16834B26] text-[#126B3D]",children:e.jsx(z,{className:"w-3.5 h-3.5"})})}),e.jsxs("div",{className:"flex-1 min-w-0",children:[e.jsx("p",{className:"text-xs font-semibold text-[#12233F] truncate",children:_.title}),e.jsx("p",{className:"text-[11px] text-[#475569] line-clamp-2 mt-0.5",children:_.subtitle}),e.jsx("span",{className:"text-[10px] text-[#64748B] mt-1 block",children:_.timestamp})]})]},_.id))}),e.jsx("div",{className:"px-4 py-2 border-t border-[#E2E8F0] bg-[#F6F8FB] text-center text-[11px] text-[#475569]",children:"Sample notices: platform/notification is not built yet."})]})]}),e.jsxs("div",{className:"relative pl-1 border-l border-[#E2E8F0]",ref:j,children:[e.jsxs("button",{onClick:()=>E(!S),className:"flex items-center gap-2.5 p-1.5 rounded-lg hover:bg-[#F1F5F9] transition-colors text-left",children:[e.jsxs("div",{className:"hidden sm:block text-right",children:[e.jsx("div",{className:"text-xs font-semibold text-[#12233F] leading-tight",children:h}),e.jsx("div",{className:"text-[11px] text-[#475569] leading-tight",children:u})]}),e.jsx("div",{className:"w-8 h-8 rounded-full bg-[#D03F1B] text-white flex items-center justify-center font-semibold text-xs overflow-hidden",children:m.photo?e.jsx("img",{src:m.photo,alt:"",className:"w-full h-full",style:{objectFit:"cover"}}):v}),e.jsx(ze,{className:"w-3.5 h-3.5 text-[#475569]"})]}),S&&e.jsxs("div",{className:"absolute right-0 mt-2 w-56 rounded-xl bg-[#FFFFFF] border border-[#E2E8F0] shadow-xl py-1.5 z-50",children:[e.jsxs("div",{className:"px-3.5 py-2.5 border-b border-[#E2E8F0] bg-[#F6F8FB]",children:[e.jsx("p",{className:"text-xs font-semibold text-[#12233F]",children:h}),e.jsx("p",{className:"text-[11px] text-[#475569] truncate",children:(o==null?void 0:o.email)??"admin@example.org"}),e.jsxs("div",{className:"mt-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#EBDCFE] text-[#6B21A8]",children:[e.jsx(de,{className:"w-3 h-3"}),o!=null&&o.is_super_admin?"Super admin · platform":o?"Organisation admin":"Preview"]})]}),e.jsxs("div",{className:"py-1",children:[e.jsxs("button",{onClick:()=>{E(!1),s("/profile")},className:"w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors",children:[e.jsx(Jn,{className:"w-3.5 h-3.5 text-[#475569]"}),e.jsx("span",{children:"Profile"})]}),e.jsxs("button",{onClick:()=>{E(!1),s("/access")},className:"w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors",children:[e.jsx(de,{className:"w-3.5 h-3.5 text-[#475569]"}),e.jsx("span",{children:"Role & Access"})]}),e.jsxs("button",{onClick:()=>{E(!1),s("/profile")},className:"w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors",children:[e.jsx(Ne,{className:"w-3.5 h-3.5 text-[#475569]"}),e.jsx("span",{children:"Security & Audit"})]})]}),e.jsx("div",{className:"border-t border-[#E2E8F0] pt-1",children:e.jsxs("button",{onClick:()=>{E(!1),i(),s("/login",{replace:!0})},className:"w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#B91C1C] hover:bg-[#DC262626]/40 transition-colors font-medium",children:[e.jsx(Wn,{className:"w-3.5 h-3.5"}),e.jsx("span",{children:"Logout"})]})})]})]})]})]}),x&&e.jsx("div",{className:"fixed inset-0 z-50 bg-black/30 backdrop-blur-xs flex items-start justify-center pt-20 px-4",onMouseDown:_=>_.target===_.currentTarget&&w(!1),children:e.jsxs("div",{className:"w-full max-w-xl bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden",children:[e.jsxs("div",{className:"flex items-center px-4 py-3 border-b border-[#E2E8F0] gap-3",children:[e.jsx(he,{className:"w-4 h-4 text-[#475569]"}),e.jsx("input",{type:"text",autoFocus:!0,placeholder:"Search pages and modules...",value:g,onChange:_=>l(_.target.value),onKeyDown:_=>_.key==="Enter"&&T[0]&&C(T[0].to),className:"w-full text-sm text-[#12233F] bg-transparent placeholder-[#64748B] focus:outline-none"}),e.jsx("button",{onClick:()=>w(!1),className:"p-1 rounded text-[#64748B] hover:text-[#12233F]",children:e.jsx(ae,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"p-3 max-h-80 overflow-y-auto space-y-2",children:[e.jsx("div",{className:"text-[11px] font-semibold uppercase text-[#475569] px-2",children:B?"Results":"Quick Navigation"}),T.map(_=>e.jsxs("button",{onClick:()=>C(_.to),className:"w-full flex items-center justify-between p-2 rounded-lg hover:bg-[#F1F5F9] text-left text-xs",children:[e.jsxs("div",{className:"flex items-center gap-2 min-w-0",children:[e.jsx("span",{className:`p-1 rounded font-medium text-[10px] ${_.tag==="NAV"?"bg-[#E7F4EC] text-[#126B3D]":"bg-[#EBDCFE] text-[#6B21A8]"}`,children:_.tag}),e.jsx("span",{className:"font-medium text-[#12233F] truncate",children:_.label})]}),e.jsx("span",{className:"text-[11px] text-[#475569]",children:"Jump →"})]},_.to)),T.length===0&&e.jsxs("p",{className:"px-2 py-3 text-xs text-[#475569]",children:['No page or module matches "',g,'".']})]}),e.jsxs("div",{className:"px-4 py-2 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-[11px] text-[#475569]",children:[e.jsx("span",{children:"Searches pages and modules. Record search needs platform/search (not built)."}),e.jsx("span",{children:"ESC to close"})]})]})}),y&&e.jsx("div",{className:"fixed inset-0 z-50 bg-black/30 backdrop-blur-xs flex items-center justify-center p-4",children:e.jsxs("div",{className:"w-full max-w-lg bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] p-6 space-y-4",children:[e.jsxs("div",{className:"flex items-center justify-between border-b border-[#E2E8F0] pb-3",children:[e.jsxs("div",{className:"flex items-center gap-2.5",children:[e.jsx("div",{className:"p-2 rounded-lg bg-[#EBDCFE] text-[#6B21A8]",children:e.jsx(qi,{className:"w-5 h-5"})}),e.jsxs("div",{children:[e.jsx("h3",{className:"font-semibold text-sm text-[#12233F]",children:"Education OS Help & Documentation"}),e.jsx("p",{className:"text-xs text-[#475569]",children:"Admin console"})]})]}),e.jsx("button",{onClick:()=>k(!1),className:"text-[#475569] hover:text-[#12233F]",children:e.jsx(ae,{className:"w-5 h-5"})})]}),e.jsxs("div",{className:"space-y-3 text-xs text-[#12233F]",children:[e.jsxs("p",{children:["Welcome to the ",e.jsx("strong",{children:"Education OS admin console"}),". Education OS is one multi-tenant platform: each organisation registers, picks its academy type and plan, and sees only its own data."]}),e.jsxs("div",{className:"p-3 rounded-lg bg-[#F1F5F9] border border-[#E2E8F0] space-y-1.5",children:[e.jsx("div",{className:"font-semibold text-[#7E22CE]",children:"Active MVP Screens:"}),e.jsxs("ul",{className:"list-disc list-inside space-y-1 text-[#475569]",children:[e.jsxs("li",{children:[e.jsx("strong",{children:"Dashboard:"})," KPIs, trends, approval queues and upcoming items (sample data)."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Users & Access:"})," Multi-department directory with sliding details drawer."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Roles & Permissions:"})," Roles from the academy profile and the permission keys each module defines."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Admissions:"})," Applicant review screen (sample data; the admissions module is not built yet)."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Role Dashboards, Module Registry, My Profile:"})," layouts, entitlement and your account, from the repo and the API."]}),e.jsxs("li",{children:[e.jsx("strong",{children:"Audit Activity:"})," Sample events using the repo's event names; the platform/audit API is not built yet."]})]})]}),e.jsx("p",{className:"text-[11px] text-[#475569]",children:"For assistance, contact your organisation admin, or the platform operator (super admin)."})]}),e.jsx("div",{className:"flex justify-end pt-2",children:e.jsx("button",{onClick:()=>k(!1),className:"px-4 py-2 rounded-lg bg-[#12233F] text-white font-medium text-xs hover:bg-[#12233F] transition-colors",children:"Close Window"})})]})})]})},Fd=()=>{const[t,n]=f.useState(!1),[s,a]=f.useState(!1),[i,o]=f.useState(!0),m=De(),p=Ht(),{session:h,preview:u}=ie(),v=h!=null&&h.trialEndsAt?new Date(h.trialEndsAt).toLocaleDateString("en-IN",{day:"numeric",month:"short",year:"numeric"}):null,g=v?{text:`Trial ends ${v} · ${p.detail}`,link:{to:"/modules",label:"See what your plan includes →"}}:u||!h?{text:"Preview mode: sample data, no API connected.",link:null}:null;return e.jsxs("div",{className:"min-h-screen bg-[#F6F8FB] flex flex-col font-sans",children:[e.jsx(ud,{collapsed:t,onToggleCollapse:()=>n(!t),mobileOpen:s,onCloseMobile:()=>a(!1)}),e.jsxs("div",{className:`flex-1 flex flex-col transition-all duration-300 ease-in-out ${t?"lg:pl-[72px]":"lg:pl-[260px]"}`,children:[i&&g&&e.jsxs("div",{className:"relative bg-[#08875D] text-white text-[13px] font-medium px-10 py-2 text-center",children:[g.text," ",g.link&&e.jsx(W,{to:g.link.to,className:"underline underline-offset-2 font-semibold hover:text-[#D1FAE5]",children:g.link.label}),e.jsx("button",{onClick:()=>o(!1),"aria-label":"Dismiss announcement",className:"absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center hover:bg-white/15",children:e.jsx(ae,{className:"w-4 h-4"})})]}),e.jsx(jd,{onToggleMobileMenu:()=>a(!s)}),e.jsx("main",{className:"flex-1 p-4 sm:p-6 max-w-7xl w-full mx-auto",children:e.jsx("div",{className:"page-enter",children:e.jsx(Bn,{})},m.pathname)}),e.jsxs("footer",{className:"py-4 px-6 border-t border-[#E2E8F0] text-center text-xs text-[#475569] flex flex-col sm:flex-row items-center justify-between gap-2",children:[e.jsxs("span",{children:["© 2026 ",p.name,". All rights reserved."]}),e.jsxs("div",{className:"flex items-center gap-4 text-[11px]",children:[e.jsx("span",{className:"text-[#64748B] font-medium",children:"Education OS"}),e.jsx("span",{className:"text-[#CBD5E1]",children:"•"}),e.jsx("span",{children:p.detail})]})]})]})]})},jt={applicant:{description:"Prospective student applying through the admissions portal.",dataScope:"Self",userCount:1842},student:{description:"Enrolled student: timetable, attendance, LMS, exams, fees and campus services.",dataScope:"Self",userCount:3414},athlete:{description:"Student-athlete. Inherits the Student dashboard, plus training, nutrition and tournaments.",dataScope:"Self",userCount:428},faculty:{description:"Teaches courses, marks attendance, grades LMS work and performs exam duties.",dataScope:"Assigned Records",userCount:312},coach:{description:"Plans training, reviews video, manages squads and books sports facilities. Inherits the Faculty dashboard.",dataScope:"Assigned Records",userCount:42},"medical-staff":{description:"Tracks injuries, physio appointments and fitness clearances.",dataScope:"Assigned Records",userCount:9},nutritionist:{description:"Builds and reviews athlete diet plans and body-composition trends.",dataScope:"Assigned Records",userCount:4},"examination-staff":{description:"Schedules exams, issues hall tickets, processes and publishes results.",dataScope:"Institution",userCount:6},"department-admin":{description:"Runs a department: approvals, faculty load, attendance and results.",dataScope:"Department",userCount:18},"finance-staff":{description:"Fee collection, payment reconciliation, budgets and purchase orders.",dataScope:"Institution",userCount:8},"hr-staff":{description:"Leave, payroll runs, joinings and exits, and e-office file movement.",dataScope:"Institution",userCount:7},"facility-staff":{description:"Bookings, maintenance tickets, stock levels and asset audits.",dataScope:"Department",userCount:21},governance:{description:"Grievances, RTI deadlines, IQAC and regulatory returns.",dataScope:"Institution",userCount:11},"support-staff":{description:"Triages tickets, watches SLA breaches, incidents and AMC renewals.",dataScope:"Assigned Records",userCount:15},management:{description:"Institution leadership: admissions, finance, results, compliance and productions at a glance.",dataScope:"Institution",userCount:5},"org-admin":{description:"Created at registration. Users, roles, settings and subscription of one organisation.",dataScope:"Institution",userCount:1},"super-admin":{description:"Platform operator outside every organisation: approves organisations and academic packages, plans, subscriptions, overrides and audited impersonation.",dataScope:"Institution",userCount:1}},Nd=new Set(Mn.map(t=>t.id));function gs(t){return Rn(t.roles).map(n=>{var s,a,i;return{id:n.id,title:n.title,description:((s=jt[n.id])==null?void 0:s.description)??"",dataScope:((a=jt[n.id])==null?void 0:a.dataScope)??"Self",userCount:((i=jt[n.id])==null?void 0:i.userCount)??0,system:Nd.has(n.id),permissions:$t([n.id],n.id==="super-admin")}})}const fs=t=>Object.fromEntries(t.flatMap(n=>lt[n.id]?[[n.id,lt[n.id]]]:[])),ys=gs(ct);function Ut(){const n=ye().profile??ct;return f.useMemo(()=>{const s=gs(n);return{ROLES:s,ROLE_LAYOUTS:fs(s),ROLES_SOURCE:`platform/identity/config/profiles/${n.profile}.yaml`,ROLES_PROFILE_TITLE:n.title}},[n])}const _d=new Map([...Object.values(Ze).flatMap(t=>Rn(t.roles).map(n=>[n.id,n.title])),...Mn.map(t=>[t.id,t.title])]),pt=t=>ys.find(n=>n.id===t),J=t=>{var n;return((n=pt(t))==null?void 0:n.title)??_d.get(t)??t},xs=fs(ys),Pe=t=>Ks(t,lt),Ie=t=>t.split(".")[0],Sd=t=>Object.keys(xs).filter(n=>Pe(n).some(s=>Ie(s)===t)),Ad=t=>[...new Set(Object.keys(xs).flatMap(Pe))].filter(n=>Ie(n)===t),bs=()=>{var t;return typeof window<"u"&&!!((t=window.matchMedia)!=null&&t.call(window,"(prefers-reduced-motion: reduce)").matches)};function et(t,n=.45,s=120){const[a,i]=f.useState(()=>typeof IntersectionObserver>"u"||bs());return f.useEffect(()=>{const o=t.current;if(a||!o)return;let m=0;const p=new IntersectionObserver(h=>{h.some(u=>u.isIntersecting)&&(p.disconnect(),m=window.setTimeout(()=>i(!0),s))},{threshold:n});return p.observe(o),()=>{p.disconnect(),window.clearTimeout(m)}},[t,a,n,s]),a}const Bt=t=>1-Math.pow(1-t,3);function vs(t,n){const s=bs(),[a,i]=f.useState(s?n:0);return f.useEffect(()=>{if(!t||s)return;let o=0;const m=performance.now(),p=h=>{const u=Math.min(n,h-m);i(u),u<n&&(o=requestAnimationFrame(p))};return o=requestAnimationFrame(p),()=>cancelAnimationFrame(o)},[t,n,s]),a}const ke=({end:t,decimals:n=0,prefix:s="",suffix:a="",duration:i=1e3,active:o=!0,delay:m=0})=>{const p=vs(o,i+m),h=Math.max(0,Math.min(1,(p-m)/i)),u=h>=1?t:t*Bt(h);return e.jsxs(e.Fragment,{children:[s,u.toLocaleString("en-IN",{minimumFractionDigits:n,maximumFractionDigits:n}),a]})},Ed={brand:"linear-gradient(90deg,rgba(112,14,92,0.94) 0%,rgba(84,24,140,0.86) 30%,rgba(55,48,163,0.45) 52%,rgba(49,46,129,0.08) 70%,transparent 82%)",violet:"linear-gradient(90deg,rgba(109,40,217,0.95) 0%,rgba(91,33,182,0.86) 30%,rgba(67,56,202,0.45) 52%,rgba(67,56,202,0.08) 70%,transparent 82%)"},Gt=({src:t=O("/campus.jpg"),position:n="62% 72%",tone:s="brand",fit:a="full"})=>a==="right"?e.jsx("div",{className:"absolute inset-y-0 right-0 w-[64%] bg-cover bg-no-repeat [mask-image:linear-gradient(to_right,transparent_0%,black_35%)]",style:{backgroundImage:`url('${t}')`,backgroundPosition:n}}):e.jsxs(e.Fragment,{children:[e.jsx("div",{className:"absolute inset-0 bg-cover bg-no-repeat",style:{backgroundImage:`url('${t}')`,backgroundPosition:n}}),e.jsx("div",{className:"absolute inset-0",style:{backgroundImage:Ed[s]}}),e.jsx("div",{className:"absolute inset-x-0 bottom-0 h-1/2 bg-[linear-gradient(to_top,rgba(17,12,48,0.35),transparent)]"})]}),Cd=({values:t,colors:n,delay:s=0})=>{const a=Math.max(...t),i=Math.min(...t);return e.jsx("div",{className:"flex items-end gap-[3px] w-24 h-[30px]","aria-hidden":!0,children:t.map((o,m)=>e.jsx("span",{className:"flex-1 rounded-t-[2px] origin-bottom eos-kpi-col",style:{height:`${30+(o-i)/(a-i||1)*70}%`,backgroundColor:n[m%n.length],animationDelay:`${s+m*90}ms`}},m))})},Md=({slices:t,delay:n=0})=>{const a=2*Math.PI*8,i=t.reduce((m,p)=>m+p.value,0)||1;let o=0;return e.jsxs("svg",{viewBox:"0 0 32 32",className:"w-8 h-8 -rotate-90","aria-hidden":!0,children:[t.map((m,p)=>{const h=m.value/i*a,u=-o;return o+=h,e.jsx("circle",{cx:"16",cy:"16",r:8,fill:"none",stroke:m.color,strokeWidth:2*8,strokeDashoffset:u,className:"eos-kpi-seg",style:{"--seg":`${h}`,"--seg-c":`${a}`,animationDelay:`${n+p*140}ms`}},p)}),e.jsx("circle",{cx:"16",cy:"16",r:"15.5",fill:"none",stroke:"#FFFFFF",strokeOpacity:"0.9",strokeWidth:"1"})]})},Rd=({stacks:t,colors:n,delay:s=0})=>{const a=Math.max(...t.map(i=>i.reduce((o,m)=>o+m,0)))||1;return e.jsx("div",{className:"flex items-end gap-[3px] w-24 h-[30px]","aria-hidden":!0,children:t.map((i,o)=>{const m=i.reduce((p,h)=>p+h,0);return e.jsx("span",{className:"flex-1 flex flex-col-reverse overflow-hidden rounded-t-[2px] origin-bottom eos-kpi-col",style:{height:`${m/a*100}%`,animationDelay:`${s+o*90}ms`},children:i.map((p,h)=>e.jsx("span",{style:{height:`${p/m*100}%`,backgroundColor:n[h%n.length]}},h))},o)})})},Pd=({slices:t,of:n,delay:s=0})=>{const i=2*Math.PI*12,o=n??(t.reduce((p,h)=>p+h.value,0)||1);let m=0;return e.jsxs("svg",{viewBox:"0 0 32 32",className:"w-8 h-8 -rotate-90","aria-hidden":!0,children:[e.jsx("circle",{cx:"16",cy:"16",r:12,fill:"none",stroke:"#E3E7EE",strokeWidth:"5"}),t.map((p,h)=>{const u=p.value/o*i,v=-m;return m+=u,e.jsx("circle",{cx:"16",cy:"16",r:12,fill:"none",stroke:p.color,strokeWidth:"5",strokeDashoffset:v,className:"eos-kpi-seg",style:{"--seg":`${Math.max(0,u-.6)}`,"--seg-c":`${i}`,animationDelay:`${s+h*140}ms`}},h)})]})},Dd=({bars:t,delay:n=0})=>{const s=Math.max(...t.map(a=>a.value))||1;return e.jsx("div",{className:"flex flex-col justify-end gap-[2.5px] w-24 h-[30px]","aria-hidden":!0,children:t.map((a,i)=>e.jsx("span",{className:"block h-1 rounded-full origin-left eos-kpi-bar",style:{width:`${a.value/s*100}%`,backgroundColor:a.color,animationDelay:`${n+i*120}ms`}},i))})},Od=({value:t,zones:n,delay:s=0})=>{const a="M6 26 A18 18 0 0 1 42 26";let i=0;return e.jsxs("svg",{viewBox:"0 0 48 30",className:"w-12 h-[30px] overflow-visible","aria-hidden":!0,children:[n.map((o,m)=>{const p=o.to-i-(m<n.length-1?.025:0),h=e.jsx("path",{d:a,fill:"none",stroke:o.color,strokeWidth:"5",pathLength:1,strokeDasharray:`${p} 1`,strokeDashoffset:-i},m);return i=o.to,h}),e.jsx("g",{className:"eos-kpi-needle",style:{"--needle":`${-90+t*180}deg`,animationDelay:`${s}ms`},children:e.jsx("line",{x1:"24",y1:"26",x2:"24",y2:"12",stroke:"#12233F",strokeWidth:"1.8",strokeLinecap:"round"})}),e.jsx("circle",{cx:"24",cy:"26",r:"2.6",fill:"#12233F"})]})},yn=[{accent:"#315EA8",chipBg:"#FFFFFF",chipFg:"#315EA8",tint:"#F3F7FD",border:"#DCE5F3"},{accent:"#159A72",chipBg:"#FFFFFF",chipFg:"#127F5E",tint:"#F1FAF6",border:"#D3EEE4"},{accent:"#E45B67",chipBg:"#FFFFFF",chipFg:"#C9414E",tint:"#FEF5F6",border:"#F7DCDF"},{accent:"#22A06B",chipBg:"#FFFFFF",chipFg:"#1B8458",tint:"#F2FAF6",border:"#D4EEE2"},{accent:"#6256C9",chipBg:"#FFFFFF",chipFg:"#5247B5",tint:"#F6F5FD",border:"#E1DEF6"},{accent:"#E89A35",chipBg:"#FFFFFF",chipFg:"#B8721A",tint:"#FEF9F2",border:"#F6E6CD"}],Bd={up:"text-[#126B3D]",alert:"text-[#B91C1C]",muted:"text-[#475569]"},Ld={navy:"bg-[var(--accent-tint)] text-[var(--accent)] ring-[var(--accent-ring)]",green:"bg-[#EEF7F1] text-[#126B3D] ring-[#CDE8D8]",orange:"bg-[#FFF8EC] text-[#A35F00] ring-[#FBE3BD]",coral:"bg-[#FEF2F2] text-[#B91C1C] ring-[#FECACA]"},Td=(t,n)=>t===0?"navy":n==="alert"?"orange":n==="up"?"green":"navy",Id=({label:t,value:n,icon:s,delta:a,deltaTone:i="up",note:o,index:m=0,accent:p,to:h,palette:u,viz:v})=>{const g=e.jsxs(e.Fragment,{children:[e.jsxs("div",{className:"flex items-start justify-between gap-2",children:[e.jsx("span",{className:"text-[13px] font-medium leading-snug text-[#5B6B82]",children:t}),u?e.jsx("span",{className:"w-9 h-9 rounded-[10px] flex items-center justify-center flex-shrink-0 shadow-[0_1px_3px_rgba(16,24,40,0.08)] transition-colors duration-200 bg-[var(--chip-bg)] text-[var(--chip-fg)] group-hover:bg-[var(--chip-fg)] group-hover:text-white",children:e.jsx(s,{className:"w-4 h-4"})}):e.jsx("span",{className:`w-8 h-8 rounded-lg ring-1 flex items-center justify-center flex-shrink-0 ${Ld[p??Td(m,i)]}`,children:e.jsx(s,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"mt-auto pt-3 flex items-end justify-between gap-4",children:[e.jsxs("div",{className:"min-w-0",children:[e.jsx("div",{className:"text-[30px] leading-none font-extrabold tracking-[-0.02em] text-[#12233F] tabular-nums break-words",children:n}),(a||o)&&e.jsxs("div",{className:"mt-2 text-[12px] leading-snug",children:[a&&e.jsxs("span",{className:`inline-flex items-center gap-1 font-semibold ${Bd[i]}`,children:[i==="alert"&&e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-[#DC2626]"}),a]}),a&&o&&e.jsx("span",{className:"text-[#CBD5E1]",children:" · "}),o&&e.jsx("span",{className:"text-[#64748B]",children:o})]})]}),v&&e.jsx("div",{className:"flex-shrink-0 w-24 h-[30px] flex items-end justify-end pb-1",children:v})]})]}),l="group relative flex flex-col h-full min-h-[150px] overflow-hidden rounded-[14px] border border-[#E4E8EF] bg-white px-6 pt-5 pb-5 min-w-0 shadow-[0_1px_2px_rgba(16,24,40,0.03)] transition-[box-shadow,border-color] duration-200 ease-out hover:border-[var(--card-ring)] hover:shadow-[0_10px_24px_-14px_var(--card-shadow)]",x={animationDelay:`${m*60}ms`,"--card-ring":u?`${u.accent}55`:"var(--accent-ring)","--card-shadow":u?`${u.accent}55`:"rgba(15,23,42,0.25)",...u?{"--chip-bg":u.chipBg,"--chip-fg":u.chipFg,backgroundColor:u.tint,borderColor:u.border}:{}};return h?e.jsx(W,{to:h,className:`${l} focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]`,style:x,children:g}):e.jsx("div",{className:l,style:x,children:g})},ce=({stats:t,label:n="Key metrics",colorful:s=!1})=>e.jsx("section",{"aria-label":n,className:`grid gap-5 grid-cols-1 min-[420px]:grid-cols-2 ${t.length>4?"md:grid-cols-3 2xl:grid-cols-6":"lg:grid-cols-4"}`,children:t.map((a,i)=>e.jsx(Id,{index:i,palette:s?yn[i%yn.length]:void 0,...a},a.label))}),me=({title:t,subtitle:n,eyebrow:s,actions:a,art:i})=>i?e.jsxs("header",{className:"eos-hero relative overflow-visible rounded-xl text-white min-h-[200px] md:min-h-[240px] flex items-end",children:[e.jsx("div",{"aria-hidden":!0,className:"pointer-events-none absolute inset-0 overflow-hidden rounded-xl",children:i}),e.jsxs("div",{className:"relative z-10 px-6 py-7 sm:px-9 max-w-[560px]",children:[s&&e.jsx("div",{className:"eos-hero-sub text-[12px] font-medium mb-1.5",children:s}),e.jsx("h1",{className:"text-[32px] leading-tight font-bold tracking-[-0.02em] text-white",children:t}),n&&e.jsx("div",{className:"eos-hero-sub text-[14px] mt-1.5",children:n}),a&&e.jsx("div",{className:"mt-5 flex flex-wrap items-center gap-2.5",children:a})]})]}):e.jsxs("header",{className:"eos-hero relative rounded-xl px-6 py-7 sm:px-8 flex flex-col md:flex-row md:items-end md:justify-between gap-5 text-white",children:[e.jsxs("div",{className:"relative z-10 min-w-0",children:[s&&e.jsx("div",{className:"eos-hero-sub text-[12px] font-medium mb-1.5",children:s}),e.jsx("h1",{className:"text-[30px] leading-tight font-bold tracking-[-0.02em] text-white",children:t}),n&&e.jsx("div",{className:"eos-hero-sub text-sm mt-1.5",children:n})]}),a&&e.jsx("div",{className:"relative z-10 flex flex-wrap items-center gap-2",children:a})]}),Fe="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-[#F65B66] text-white text-[13px] font-semibold hover:bg-[#E9505C] transition-colors eos-btn-primary",se="inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-white border border-[#E2E8F0] text-xs font-semibold text-[#12233F] hover:border-[#CBD5E1] hover:bg-[#F6F8FB] transition-colors eos-btn-secondary",H="bg-white border border-[#E2E8F0] rounded-xl",G=({title:t,subtitle:n,action:s})=>e.jsxs("div",{className:"flex items-start justify-between gap-4 px-5 pt-4 pb-3",children:[e.jsxs("div",{className:"min-w-0",children:[e.jsx("h2",{className:"text-[15px] font-semibold text-[#12233F]",children:t}),n&&e.jsx("p",{className:"text-xs text-[#64748B] mt-0.5",children:n})]}),s]}),ws=t=>null,ks=t=>null,js=t=>null,ut=t=>null,Wt=t=>null,Yt=t=>null;function $d({width:t="100%",height:n="100%",children:s}){const a=f.useRef(null),[i,o]=f.useState(null);f.useLayoutEffect(()=>{const p=a.current;if(!p)return;const h=()=>o({w:p.clientWidth,h:p.clientHeight});h();const u=new ResizeObserver(h);return u.observe(p),()=>u.disconnect()},[]);const m=et(a);return e.jsx("div",{ref:a,className:"recharts-responsive-container",style:{width:t,height:n,minWidth:0},children:e.jsx("div",{style:{width:0,height:0,overflow:"visible"},children:i&&i.w>0&&i.h>0&&f.cloneElement(s,{width:i.w,height:i.h,active:m})})})}function Fs(t){const n=[];return f.Children.forEach(t,s=>{f.isValidElement(s)&&(s.type===f.Fragment?n.push(...Fs(s.props.children)):n.push(s))}),n}function We(t,n){var s;return(s=t.find(a=>a.type===n))==null?void 0:s.props}function ht(t,n){return t.filter(s=>s.type===n).map(s=>s.props)}const gt=t=>Number(t.toPrecision(12));function Vd(t,n){if(t<=0)return 0;const s=Math.floor(Math.log10(t))+1,a=10**s,i=t/a,o=s!==1?.05:.1;return gt((Math.ceil(gt(i/o))+n)*o*a)}function Ns(t,n=5,s=0){if(t<=0)return[0,1,2,3,4].slice(0,n);const a=Vd(t/(n-1),s);let i=Math.ceil(gt(t/a));const o=i+1;return o>n?Ns(t,n,s+1):(o<n&&(i+=n-o),Array.from({length:i+1},(m,p)=>gt(p*a)))}function xn(t){let n=document.getElementById("recharts_measurement_span");n||(n=document.createElement("span"),n.id="recharts_measurement_span",n.setAttribute("aria-hidden","true"),document.body.appendChild(n)),Object.assign(n.style,{position:"absolute",top:"-20000px",left:0,padding:0,margin:0,border:"none",whiteSpace:"pre"}),n.textContent=t;const s=n.getBoundingClientRect();return{width:s.width,height:s.height}}function bn(t,n,s,a){const i=t.length>=2&&Math.sign(t[1]-t[0])||1,[o,m]=i===1?[s,a]:[a,s];let p=m;const h=[];for(let u=t.length-1;u>=0;u--){const v=n[u];let g=t[u];if(u===t.length-1){const x=i*(g+i*v/2-p);x>0&&(g-=x*i)}!(i*g<i*o||i*g>i*p)&&i*(g-i*v/2-o)>=0&&i*(g+i*v/2-p)<=0&&(p=g-i*(v/2+5),h.push({i:u,at:g}))}return h.reverse()}const qd=()=>{var t;return typeof window<"u"&&!!((t=window.matchMedia)!=null&&t.call(window,"(prefers-reduced-motion: reduce)").matches)},Y=t=>Math.round(t*1e3)/1e3,at=t=>Math.round(t*1e4)/1e4;function vn(t){const n=t.length;if(n===0)return"";if(n===1)return`M${Y(t[0].x)},${Y(t[0].y)}`;if(n===2)return`M${Y(t[0].x)},${Y(t[0].y)}L${Y(t[1].x)},${Y(t[1].y)}`;const s=p=>p<0?-1:1,a=(p,h,u,v,g,l)=>{const x=u-p,w=g-u,N=(v-h)/(x||(w<0?-0:0)),b=(l-v)/(w||(x<0?-0:0)),S=(N*w+b*x)/(x+w);return(s(N)+s(b))*Math.min(Math.abs(N),Math.abs(b),.5*Math.abs(S))||0},i=(p,h,u,v,g)=>{const l=u-p;return l?(3*(v-h)/l-g)/2:g},o=new Array(n);for(let p=1;p<n-1;p++)o[p]=a(t[p-1].x,t[p-1].y,t[p].x,t[p].y,t[p+1].x,t[p+1].y);o[0]=i(t[0].x,t[0].y,t[1].x,t[1].y,o[1]),o[n-1]=i(t[n-2].x,t[n-2].y,t[n-1].x,t[n-1].y,o[n-2]);let m=`M${Y(t[0].x)},${Y(t[0].y)}`;for(let p=0;p<n-1;p++){const h=t[p],u=t[p+1],v=(u.x-h.x)/3;m+=`C${Y(h.x+v)},${Y(h.y+v*o[p])},${Y(u.x-v)},${Y(u.y-v*o[p+1])},${Y(u.x)},${Y(u.y)}`}return m}function Hd(t,n,s,a){const i=3*t,o=3*(s-t)-i,m=1-i-o,p=3*n,h=3*(a-n)-p,u=1-p-h,v=x=>((m*x+o)*x+i)*x,g=x=>((u*x+h)*x+p)*x,l=x=>(3*m*x+2*o)*x+i;return x=>{let w=x;for(let N=0;N<8;N++){const b=v(w)-x,S=l(w);if(Math.abs(b)<1e-6||Math.abs(S)<1e-6)break;w-=b/S}return g(Math.min(1,Math.max(0,w)))}}const Ud=Hd(.25,.1,.25,1);function Gd(t,n=!0){var o;const s=typeof window<"u"&&((o=window.matchMedia)==null?void 0:o.call(window,"(prefers-reduced-motion: reduce)").matches),[a,i]=f.useState(s?1:0);return f.useEffect(()=>{if(s||!n)return;let m=0;const p=performance.now(),h=u=>{const v=Math.min(1,(u-p)/t);i(Ud(v)),v<1&&(m=requestAnimationFrame(h))};return m=requestAnimationFrame(h),()=>cancelAnimationFrame(m)},[t,s,n]),a}function Wd(t,n,s,a,i){if(a<=0||s<=0)return"";const o=Math.min(i,s/2,a);return[t,n,s,a]=[at(t),at(n),at(s),at(a)],`M${t},${n+o}A${o},${o},0,0,1,${t+o},${n}L${t+s-o},${n}A${o},${o},0,0,1,${t+s},${n+o}L${t+s},${n+a}L${t},${n+a}Z`}function _s(t,n){const{data:s,width:a=0,height:i=0}=n,o={top:5,right:5,left:5,bottom:5,...n.margin},m=Fs(n.children),p=We(m,ws)??{},h=We(m,ks)??{},u=(t==="bar"?ht(m,Wt):ht(m,Yt)).map(k=>k.dataKey),v=h.width??60,g=p.height??30,l={left:o.left+v,top:o.top,width:Math.max(0,a-o.left-o.right-v),height:Math.max(0,i-o.top-o.bottom-g)},x=Math.max(0,...s.flatMap(k=>u.map(B=>Number(k[B])||0))),w=Ns(x),N=w[w.length-1]||1,b=k=>l.top+l.height-k/N*l.height,S=s.length,E=S?l.width/S:0;return{items:m,x:p,y:h,frame:l,ticks:w,yOf:b,xOf:k=>t==="bar"?l.left+E*k+E/2:l.left+(S>1?l.width*k/(S-1):l.width/2),band:E,n:S}}function Ss({chart:t,draw:n=1}){const{frame:s,ticks:a,yOf:i,items:o}=t,m=We(o,js);return m?e.jsx("g",{className:"recharts-cartesian-grid",children:e.jsx("g",{className:"recharts-cartesian-grid-horizontal",children:a.map(p=>e.jsx("line",{stroke:m.stroke??"#ccc",fill:"none",x1:s.left,y1:i(p),x2:s.left+s.width*n,y2:i(p)},p))})}):null}function As({chart:t}){const{x:n,frame:s}=t;if(n.axisLine===!1)return null;const a=(typeof n.axisLine=="object"?n.axisLine.stroke:void 0)??n.stroke??"#666",i=s.top+s.height;return e.jsx("g",{className:"recharts-layer recharts-cartesian-axis recharts-xAxis xAxis",children:e.jsx("line",{className:"recharts-cartesian-axis-line",stroke:a,fill:"none",x1:s.left,y1:i,x2:s.left+s.width,y2:i})})}function Es({chart:t,labels:n,width:s,height:a}){const{x:i,y:o,frame:m,ticks:p,yOf:h,xOf:u,n:v}=t,g=o.tickFormatter??(b=>String(b)),l=p.map(b=>g(b)),x=bn(Array.from({length:v},(b,S)=>u(S)),n.map(b=>xn(b).width),0,s),w=bn(p.map(b=>h(b)),l.map(b=>xn(b).height),0,a),N=m.top+m.height+8;return e.jsxs(e.Fragment,{children:[e.jsx("g",{className:"recharts-layer recharts-cartesian-axis-tick-labels recharts-xAxis-tick-labels",children:x.map(({i:b,at:S})=>e.jsx("text",{className:"recharts-text recharts-cartesian-axis-tick-value",x:S,y:N,textAnchor:"middle",fontSize:i.fontSize,fill:i.stroke??"#666",stroke:"none",children:e.jsx("tspan",{x:S,dy:"0.71em",children:n[b]})},b))}),e.jsx("g",{className:"recharts-layer recharts-cartesian-axis-tick-labels recharts-yAxis-tick-labels",children:w.map(({i:b,at:S})=>e.jsx("text",{className:"recharts-text recharts-cartesian-axis-tick-value",x:m.left-8,y:S,textAnchor:"end",fontSize:o.fontSize,fill:o.stroke??"#666",stroke:"none",children:e.jsx("tspan",{x:m.left-8,dy:"0.355em",children:l[b]})},b))})]})}function Cs({tip:t,frame:n,at:s,label:a,entries:i}){const o=f.useRef(null),[m,p]=f.useState(null);f.useLayoutEffect(()=>{if(!s||!o.current)return;const{width:u,height:v}=o.current.getBoundingClientRect(),g=(l,x,w,N)=>{const b=l+10;return b+x>w+N?Math.max(l-10-x,w):Math.max(b,w)};p({x:g(s.x,u,n.left,n.width),y:g(s.y,v,n.top,n.height)})},[s,n.left,n.top,n.width,n.height,a]);const h=t.formatter??((u,v)=>[String(u),String(v)]);return e.jsx("div",{className:"recharts-tooltip-wrapper",style:{visibility:s&&m?"visible":"hidden",pointerEvents:"none",position:"absolute",top:0,left:0,outline:"none",transform:m?`translate(${m.x}px, ${m.y}px)`:void 0,transition:s&&m&&!qd()?"transform 400ms ease":void 0},children:e.jsxs("div",{ref:o,className:"recharts-default-tooltip",role:"status","aria-live":"assertive",style:{margin:0,padding:10,backgroundColor:"#fff",border:"1px solid #ccc",whiteSpace:"nowrap",...t.contentStyle},children:[e.jsx("p",{className:"recharts-tooltip-label",style:{margin:0,...t.labelStyle},children:t.labelFormatter?t.labelFormatter(a):String(a)}),e.jsx("ul",{className:"recharts-tooltip-item-list",style:{padding:0,margin:0},children:i.map(u=>{const[v,g]=h(u.value,u.name);return e.jsxs("li",{className:"recharts-tooltip-item",style:{display:"block",paddingTop:4,paddingBottom:4,...t.itemStyle},children:[e.jsx("span",{className:"recharts-tooltip-item-name",children:g}),e.jsx("span",{className:"recharts-tooltip-item-separator",children:" : "}),e.jsx("span",{className:"recharts-tooltip-item-value",children:v}),e.jsx("span",{className:"recharts-tooltip-item-unit"})]},u.name)})})]})})}function Ms(t,n){const[s,a]=f.useState(null);return{hover:s,onMove:o=>{const m=o.currentTarget.getBoundingClientRect(),p=o.clientX-m.left,h=o.clientY-m.top,{frame:u,n:v,band:g}=t;if(!v||p<u.left||p>u.left+u.width||h<u.top||h>u.top+u.height){a(null);return}const l=n==="bar"?Math.min(v-1,Math.floor((p-u.left)/g)):Math.round((p-u.left)/(u.width||1)*(v-1));a({i:Math.max(0,l),y:h})},onLeave:()=>a(null)}}function Rs({width:t,height:n,children:s,svg:a}){return e.jsxs("div",{className:"recharts-wrapper",style:{position:"relative",cursor:"default",width:t,height:n},children:[s,a]})}function Yd(t){var Z,X;const n=_s("bar",t),{items:s,frame:a,yOf:i,band:o,n:m,x:p}=n,h=ht(s,Wt),u=We(s,ut),v=500,g=1e3,l=140,x=110,w=vs(t.active??!0,v+g+l*Math.max(0,n.n-1)+x*2),N=Bt(Math.min(1,w/v)),b=(V,ee=0)=>Bt(Math.max(0,Math.min(1,(w-v*.6-V*l-ee*x)/g))),{hover:S,onMove:E,onLeave:y}=Ms(n,"bar"),{data:k,width:B=0,height:T=0,barGap:C=4}=t,M=k.map(V=>String(V[p.dataKey??""]??"")),j=typeof t.barCategoryGap=="string"?parseFloat(t.barCategoryGap)/100:(t.barCategoryGap??.1*o)/(o||1),P=o*j;let R=C;o-2*P-(h.length-1)*R<=0&&(R=0);let _=(o-2*P-(h.length-1)*R)/Math.max(1,h.length);_>1&&(_=Math.round(_));const D=Math.min(_,((Z=h[0])==null?void 0:Z.maxBarSize)??1/0),I=a.top+a.height,pe=e.jsxs("svg",{className:"recharts-surface",width:B,height:T,viewBox:`0 0 ${B} ${T}`,style:{width:"100%",height:"100%",display:"block"},onMouseMove:E,onMouseLeave:y,children:[e.jsx(Ss,{chart:n,draw:N}),u&&S&&e.jsx("rect",{className:"recharts-tooltip-cursor",x:a.left+o*S.i,y:a.top,width:o,height:a.height,fill:((X=u.cursor)==null?void 0:X.fill)??"#ccc",stroke:"none",pointerEvents:"none"}),h.map((V,ee)=>e.jsx("g",{className:"recharts-layer recharts-bar",children:k.map((te,re)=>{var Ae;const _e=Number(te[V.dataKey])||0,Se=(I-i(_e))*b(re,ee),Be=a.left+o*re+P+h.length*(_-D)/2+(D+R)*ee,xe=S&&S.i!==re;return e.jsx("path",{className:"recharts-rectangle",fill:V.fill,fillOpacity:xe?.55:1,style:{transition:"fill-opacity 160ms ease"},d:Wd(Be,I-Se,D,Se,((Ae=V.radius)==null?void 0:Ae[0])??0)},re)})},V.dataKey)),e.jsx(As,{chart:n}),e.jsx(Es,{chart:n,labels:M,width:B,height:T})]});return e.jsx(Rs,{width:B,height:T,svg:pe,children:u&&m>0&&e.jsx(Cs,{tip:u,frame:a,at:S?{x:n.xOf(S.i),y:S.y}:null,label:S?M[S.i]:"",entries:S?h.map(V=>({name:V.name??V.dataKey,value:k[S.i][V.dataKey]})):[]})})}let zd=0;function Kd(t){var T,C;const n=_s("area",t),{items:s,frame:a,yOf:i,xOf:o,n:m,x:p}=n,h=ht(s,Yt),u=We(s,ut),v=s.filter(M=>M.type==="defs"),g=Gd(((T=h[0])==null?void 0:T.animationDuration)??1500,t.active??!0),{hover:l,onMove:x,onLeave:w}=Ms(n,"area"),[N]=f.useState(()=>`eos-area-clip-${++zd}`),{data:b,width:S=0,height:E=0}=t,y=b.map(M=>String(M[p.dataKey??""]??"")),k=a.top+a.height,B=e.jsxs("svg",{className:"recharts-surface",width:S,height:E,viewBox:`0 0 ${S} ${E}`,style:{width:"100%",height:"100%",display:"block"},onMouseMove:x,onMouseLeave:w,children:[v,e.jsx("defs",{children:e.jsx("clipPath",{id:N,children:e.jsx("rect",{x:a.left,y:0,width:(a.width+1)*g,height:E})})}),e.jsx(Ss,{chart:n}),h.map(M=>{const j=b.map((D,I)=>({x:o(I),y:i(Number(D[M.dataKey])||0)})),P=vn(j),R=vn(j.map(D=>({x:D.x,y:k})).reverse()),_=j.length?`${P}L${R.slice(1)}Z`:"";return e.jsxs("g",{className:"recharts-layer recharts-area",clipPath:g<1?`url(#${N})`:void 0,children:[e.jsx("path",{className:"recharts-curve recharts-area-area",d:_,fill:M.fill,stroke:"none",fillOpacity:.6}),e.jsx("path",{className:"recharts-curve recharts-area-curve",d:P,stroke:M.stroke,strokeWidth:M.strokeWidth??1,fill:"none"})]},M.dataKey)}),e.jsx(As,{chart:n}),u&&l&&e.jsx("path",{className:"recharts-curve recharts-tooltip-cursor",stroke:((C=u.cursor)==null?void 0:C.stroke)??"#ccc",strokeWidth:1,fill:"none",pointerEvents:"none",d:`M${o(l.i)},${a.top}L${o(l.i)},${k}`}),l&&h.map(M=>{var j,P,R;return e.jsx("circle",{className:"recharts-dot",cx:o(l.i),cy:i(Number(b[l.i][M.dataKey])||0),r:((j=M.activeDot)==null?void 0:j.r)??4,fill:M.stroke,strokeWidth:((P=M.activeDot)==null?void 0:P.strokeWidth)??2,stroke:((R=M.activeDot)==null?void 0:R.stroke)??"#fff"},M.dataKey)}),e.jsx(Es,{chart:n,labels:y,width:S,height:E})]});return e.jsx(Rs,{width:S,height:E,svg:B,children:u&&m>0&&e.jsx(Cs,{tip:u,frame:a,at:l?{x:o(l.i),y:l.y}:null,label:l?y[l.i]:"",entries:l?h.map(M=>({name:M.name??M.dataKey,value:b[l.i][M.dataKey]})):[]})})}const Ps={accent:"#4338CA",tint:"#EEEEFD",ring:"#DCDCFB",gradient:"linear-gradient(100deg, #8A1170 0%, #5B21B6 55%, #3730A3 100%)",series:["#4338CA","#059669","#DB2777"],bar:"linear-gradient(90deg, #3730A3, #4F46E5)"},Qd={"student-lifecycle":{accent:"#6D28D9",tint:"#F3EEFF",ring:"#E4D8FD",gradient:"linear-gradient(100deg, #6D28D9 0%, #5B21B6 50%, #4338CA 100%)",series:["#7C3AED","#F59E0B","#0EA5E9"],bar:"linear-gradient(90deg, #6D28D9, #8B5CF6)"},academics:{accent:"#1D4ED8",tint:"#EEF4FF",ring:"#D6E4FF",gradient:"linear-gradient(100deg, #1E40AF 0%, #1D4ED8 50%, #0E7490 100%)",series:["#2563EB","#F59E0B","#14B8A6"],bar:"linear-gradient(90deg, #1D4ED8, #3B82F6)"},sports:{accent:"#C2410C",tint:"#FFF3EC",ring:"#FEDDC8",gradient:"linear-gradient(100deg, #C2410C 0%, #B91C1C 55%, #9D174D 100%)",series:["#EA580C","#0EA5E9","#7C3AED"],bar:"linear-gradient(90deg, #C2410C, #F97316)"},facilities:{accent:"#0F766E",tint:"#ECFAF8",ring:"#C9F0EA",gradient:"linear-gradient(100deg, #0F766E 0%, #0E7490 55%, #1E40AF 100%)",series:["#0D9488","#F59E0B","#6366F1"],bar:"linear-gradient(90deg, #0F766E, #14B8A6)"},"finance-operations":{accent:"#047857",tint:"#ECFDF5",ring:"#C9F2DF",gradient:"linear-gradient(100deg, #065F46 0%, #047857 50%, #0F766E 100%)",series:["#059669","#8B5CF6","#F59E0B"],bar:"linear-gradient(90deg, #047857, #10B981)"},"campus-life":{accent:"#B45309",tint:"#FFF8EB",ring:"#FCE7C3",gradient:"linear-gradient(100deg, #B45309 0%, #C2410C 50%, #BE185D 100%)",series:["#D97706","#6366F1","#0EA5E9"],bar:"linear-gradient(90deg, #B45309, #F59E0B)"},governance:{accent:"#3730A3",tint:"#EEF0FF",ring:"#DADDFE",gradient:"linear-gradient(100deg, #312E81 0%, #3730A3 50%, #4C1D95 100%)",series:["#4F46E5","#14B8A6","#F59E0B"],bar:"linear-gradient(90deg, #3730A3, #6366F1)"},support:{accent:"#0369A1",tint:"#EEF8FE",ring:"#CDEBFB",gradient:"linear-gradient(100deg, #075985 0%, #0369A1 50%, #0E7490 100%)",series:["#0284C7","#F97316","#8B5CF6"],bar:"linear-gradient(90deg, #0369A1, #0EA5E9)"}},Ds=t=>t&&Qd[t]||Ps,Jd=t=>{var n;return Ds(t?(n=Ge(t))==null?void 0:n.suiteId:void 0)},Os=f.createContext(Ps),Xd=()=>f.useContext(Os),Bs=({theme:t,children:n,className:s})=>e.jsx(Os.Provider,{value:t,children:e.jsx("div",{className:s,style:{"--accent":t.accent,"--accent-tint":t.tint,"--accent-ring":t.ring,"--hero-gradient":t.gradient,"--accent-bar":t.bar},children:n})}),wn={contentStyle:{backgroundColor:"#FFFFFF",border:"1px solid #E2E8F0",borderRadius:"8px",fontSize:"12px",color:"#12233F",boxShadow:"0 4px 12px rgba(15, 23, 42, 0.08)"},itemStyle:{color:"#334155"},labelStyle:{color:"#12233F",fontWeight:600}},kn=({onClick:t,children:n})=>e.jsxs("button",{onClick:t,className:"inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:opacity-80 pt-0.5 whitespace-nowrap",children:[n,e.jsx(ge,{className:"w-3.5 h-3.5"})]}),zt=({title:t,subtitle:n,data:s,xKey:a,series:i,tooltipLabel:o,footer:m,className:p="",height:h=300})=>{const[u,v]=f.useState("bars"),g=f.useRef(null),l=et(g),x=Xd().series,w=E=>`g-${t.replace(/\W+/g,"-")}-${E}`,N=E=>o?o(String(E)):String(E),b=(E,y)=>[Number(E).toLocaleString("en-IN"),String(y)],S=e.jsxs(e.Fragment,{children:[e.jsx(js,{stroke:"#F1F5F9",vertical:!1}),e.jsx(ws,{dataKey:a,stroke:"#64748B",fontSize:12,tickLine:!1,axisLine:{stroke:"#E2E8F0"}}),e.jsx(ks,{stroke:"#64748B",fontSize:12,tickLine:!1,axisLine:!1,width:48,tickFormatter:E=>E.toLocaleString("en-IN")})]});return e.jsxs("section",{ref:g,className:`${H} flex flex-col eos-enter ${l?"is-in":""} ${p}`,children:[e.jsx(G,{title:t,subtitle:n,action:e.jsx("div",{className:"flex items-center gap-1 rounded-lg bg-[#F1F5F9] p-0.5 text-xs",role:"tablist","aria-label":"Chart view",children:["bars","trend"].map(E=>e.jsx("button",{role:"tab","aria-selected":u===E,onClick:()=>v(E),className:`px-2.5 py-1 rounded-md font-medium capitalize transition-colors ${u===E?"bg-white text-[#12233F] shadow-[0_1px_2px_rgba(15,23,42,0.08)]":"text-[#64748B] hover:text-[#12233F]"}`,children:E},E))})}),i.length>1&&e.jsx("div",{className:"px-5 flex flex-wrap items-center gap-4 text-[12px] text-[#475569]",children:i.map((E,y)=>e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx("span",{className:"w-2.5 h-2.5 rounded-sm",style:{background:x[y]}}),E.name]},E.key))}),e.jsx("div",{className:"px-5 pt-3 pb-4 flex-1",children:e.jsx("div",{className:"w-full",style:{height:h},role:"img","aria-label":`${u==="bars"?"Bar chart":"Trend"}: ${t}`,children:e.jsx($d,{width:"100%",height:"100%",children:u==="bars"?e.jsxs(Yd,{data:s,margin:{top:8,right:8,left:0,bottom:0},barCategoryGap:"28%",barGap:4,children:[S,e.jsx(ut,{cursor:{fill:"rgba(148, 163, 184, 0.08)"},formatter:b,labelFormatter:N,...wn}),i.map((E,y)=>e.jsx(Wt,{dataKey:E.key,name:E.name,fill:x[y],radius:[4,4,0,0],maxBarSize:40,animationDuration:700},E.key))]}):e.jsxs(Kd,{data:s,margin:{top:8,right:8,left:0,bottom:0},children:[e.jsx("defs",{children:i.map((E,y)=>e.jsxs("linearGradient",{id:w(E.key),x1:"0",y1:"0",x2:"0",y2:"1",children:[e.jsx("stop",{offset:"0%",stopColor:x[y],stopOpacity:.16}),e.jsx("stop",{offset:"100%",stopColor:x[y],stopOpacity:0})]},E.key))}),S,e.jsx(ut,{formatter:b,labelFormatter:N,...wn}),i.map((E,y)=>e.jsx(Yt,{type:"monotone",dataKey:E.key,name:E.name,stroke:x[y],strokeWidth:2,fill:`url(#${w(E.key)})`,activeDot:{r:5,strokeWidth:2,stroke:"#FFFFFF"},animationDuration:700},E.key))]})})})}),m]})},Kt=({title:t,subtitle:n,items:s,action:a,footer:i,relativeToFirst:o,unit:m="",className:p=""})=>{var g;const h=o?((g=s[0])==null?void 0:g.count)||1:Math.max(1,...s.map(l=>l.count)),u=f.useRef(null),v=et(u);return e.jsxs("section",{ref:u,className:`${H} flex flex-col eos-enter ${v?"is-in":""} ${p}`,style:{"--enter-delay":"120ms"},children:[e.jsx(G,{title:t,subtitle:n,action:a}),e.jsx("div",{className:"px-5 pt-1 pb-4 space-y-4 flex-1",children:s.map((l,x)=>{const w=Math.round(l.count/h*1e3)/10,N=250+x*160;return e.jsxs("div",{className:"space-y-1.5",children:[e.jsxs("div",{className:"flex items-center justify-between text-[13px] gap-3",children:[e.jsxs("span",{className:"text-[#334155] truncate inline-flex items-center gap-2",children:[l.color&&e.jsx("span",{className:"w-2 h-2 rounded-full flex-shrink-0",style:{background:l.color},"aria-hidden":!0}),l.label]}),e.jsxs("span",{className:"whitespace-nowrap",children:[e.jsxs("span",{className:"font-semibold text-[#12233F] tabular-nums",children:[e.jsx(ke,{end:l.count,active:v,duration:1e3,delay:N}),m]}),o&&e.jsxs("span",{className:"text-[11px] text-[#64748B] ml-1.5 tabular-nums",style:{opacity:v?1:0,transition:`opacity 400ms ease ${N+300}ms`},children:[w,"%"]})]})]}),e.jsx("div",{className:"w-full h-1.5 bg-[#F1F5F9] rounded-full overflow-hidden",children:e.jsx("div",{className:`h-full rounded-full eos-fill eos-sheen ${v?"is-in":""}`,style:{width:v?`${w}%`:0,backgroundImage:l.color?`linear-gradient(90deg, ${l.color}99, ${l.color})`:"var(--accent-bar)",transitionDelay:`${N}ms`,"--sheen-delay":`${N+900}ms`}})})]},l.label)})}),i&&e.jsxs("div",{className:"px-5 py-3 border-t border-[#F1F5F9] flex items-center justify-between text-xs",children:[e.jsx("span",{className:"text-[#475569]",children:i.label}),e.jsx("span",{className:"font-semibold text-[#12233F]",children:i.value})]})]})},Zd={Urgent:"text-[#B91C1C]",Pending:"text-[#8A4F00]",Review:"text-[#475569]",Approved:"text-[#126B3D]"},ec=({items:t,onOpen:n})=>e.jsxs("section",{className:H,children:[e.jsx(G,{title:"Action Required",subtitle:`${t.length} items awaiting your decision`}),e.jsx("ul",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:t.map(s=>e.jsx("li",{children:e.jsxs("button",{onClick:()=>n(s),className:"w-full text-left px-5 py-3 flex items-start justify-between gap-4 hover:bg-[#F6F8FB] group",children:[e.jsxs("div",{className:"min-w-0",children:[e.jsxs("div",{className:"flex items-center gap-2 text-[11px]",children:[e.jsx("span",{className:"font-mono text-[#475569]",children:s.ref}),e.jsx("span",{className:"text-[#CBD5E1]",children:"·"}),e.jsx("span",{className:"text-[#475569]",children:s.type}),e.jsx("span",{className:`font-medium ${Zd[s.urgency]}`,children:s.urgency})]}),e.jsx("p",{className:"text-[13px] font-medium text-[#12233F] mt-0.5 truncate",children:s.title}),e.jsx("p",{className:"text-xs text-[#64748B] truncate",children:s.description})]}),e.jsxs("div",{className:"flex items-center gap-2 flex-shrink-0 pt-0.5",children:[e.jsx("span",{className:"text-[11px] text-[#64748B] whitespace-nowrap",children:s.time}),e.jsx(ge,{className:"w-3.5 h-3.5 text-[#64748B] group-hover:text-[#DC3545]"})]})]})},s.id))})]}),jn={urgent:{fg:"#B91C1C",bg:"#FEF2F2"},pending:{fg:"#8A4F00",bg:"#FEF3E2"},normal:{fg:"#475569",bg:"#F1F5F9"}},tc={urgent:"Urgent",pending:"Pending",normal:"Open"};function Ls({value:t,options:n,onChange:s,label:a}){return e.jsx("div",{className:"flex items-center gap-1 rounded-lg bg-[#F1F5F9] p-0.5 text-xs",role:"tablist","aria-label":a,children:n.map(([i,o])=>e.jsx("button",{role:"tab","aria-selected":t===i,onClick:()=>s(i),className:`px-2.5 py-1 rounded-md font-medium capitalize transition-colors ${t===i?"bg-white text-[#12233F] shadow-[0_1px_2px_rgba(15,23,42,0.08)]":"text-[#64748B] hover:text-[#12233F]"}`,children:o},i))})}const nc=({rows:t,action:n,className:s=""})=>{const[a,i]=f.useState("all"),o=f.useRef(null),m=et(o),p=t.filter(g=>a==="all"||g.level===a),h=t.reduce((g,l)=>g+l.count,0),u=p.reduce((g,l)=>g+l.count,0),v=Math.max(1,...t.map(g=>g.count));return e.jsxs("section",{ref:o,className:`${H} flex flex-col eos-enter ${m?"is-in":""} ${s}`,children:[e.jsx(G,{title:"Action Required",subtitle:a==="all"?`${h} items awaiting decision`:`${u} of ${h} items · ${a}`,action:n??e.jsx(Ls,{label:"Filter queues",value:a,onChange:i,options:[["all","All"],["urgent","Urgent"],["pending","Pending"]]})}),e.jsxs("ul",{className:`px-2 pb-2 flex-1 eos-reveal ${m?"is-in":""}`,children:[p.map((g,l)=>{const x=g.tone??jn[g.level],w=jn[g.level],N=g.icon??ge;return e.jsx("li",{style:{"--i":l},children:e.jsxs("button",{onClick:g.onOpen,className:"w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-[#F6F8FB] group",children:[e.jsx("span",{className:"w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 eos-pop-in",style:{background:x.bg,color:x.fg},"aria-hidden":!0,children:e.jsx(N,{className:"w-4 h-4"})}),e.jsxs("span",{className:"flex-1 min-w-0",children:[e.jsx("span",{className:"block text-[13px] text-[#12233F] truncate",children:g.label}),e.jsx("span",{className:"block mt-1 h-1.5 w-full bg-[#F1F5F9] rounded-full overflow-hidden",children:e.jsx("span",{className:"block h-full rounded-full eos-fill",style:{width:m?`${g.count/v*100}%`:0,background:x.fg,transitionDelay:`${350+l*110}ms`}})})]}),e.jsx("span",{className:"text-[11px] font-medium px-2 py-0.5 rounded-full",style:{background:w.bg,color:w.fg},children:tc[g.level]}),e.jsx("span",{className:"w-8 text-right text-[14px] font-semibold text-[#12233F] tabular-nums",children:g.count}),e.jsx(ge,{className:"w-3.5 h-3.5 text-[#CBD5E1] group-hover:text-[#DC3545]"})]})},g.label)}),p.length===0&&e.jsxs("li",{className:"px-3 py-8 text-center text-xs text-[#64748B]",children:["Nothing ",a," right now."]})]},a)]})},sc=864e5,ac=()=>{const t=new Date;return t.setHours(0,0,0,0),t},Ft=t=>Math.round((new Date(`${t}T00:00:00`).getTime()-ac().getTime())/sc),ic=t=>t<=0?"Today":t===1?"Tomorrow":`In ${t} days`,rc=({items:t,className:n=""})=>{const[s,a]=f.useState("all"),i=f.useRef(null),o=et(i),m=[...t].sort((h,u)=>h.date.localeCompare(u.date)).filter(h=>Ft(h.date)>=0),p=m.filter(h=>{const u=Ft(h.date);return s==="all"||(s==="week"?u<=7:u>7)});return e.jsxs("section",{ref:i,className:`${H} flex flex-col eos-enter ${o?"is-in":""} ${n}`,style:{"--enter-delay":"120ms"},children:[e.jsx(G,{title:"Upcoming",subtitle:`Next two weeks · ${m.length} scheduled`,action:e.jsx(Ls,{label:"Filter upcoming",value:s,onChange:a,options:[["all","All"],["week","This week"],["later","Later"]]})}),e.jsxs("ul",{className:`px-5 pb-3 flex-1 divide-y divide-[#F1F5F9] eos-reveal ${o?"is-in":""}`,children:[p.map((h,u)=>{const v=new Date(`${h.date}T00:00:00`),g=Ft(h.date),l=h.tone??{fg:"var(--accent)",bg:"var(--accent-tint)"},x=g<=2,w=e.jsxs(e.Fragment,{children:[e.jsxs("div",{className:"w-11 flex-shrink-0 text-center rounded-lg py-1",style:{background:l.bg,boxShadow:`inset 0 0 0 1px ${l.fg}33`},children:[e.jsx("div",{className:"text-[15px] leading-none font-bold tabular-nums",style:{color:l.fg},children:v.getDate().toString().padStart(2,"0")}),e.jsx("div",{className:"text-[10px] mt-0.5 font-medium uppercase text-[#64748B]",children:v.toLocaleDateString("en-GB",{month:"short"})})]}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsx("p",{className:"text-[13px] font-medium text-[#12233F] truncate",children:h.title}),e.jsx("p",{className:"text-xs text-[#64748B] truncate",children:h.meta})]}),e.jsx("span",{className:"text-[11px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap eos-slide-in",style:x?{background:"#FEF2F2",color:"#B91C1C"}:{background:l.bg,color:l.fg},title:h.category,children:ic(g)})]});return e.jsx("li",{style:{"--i":u},children:h.onOpen?e.jsxs("button",{onClick:h.onOpen,className:"w-full flex items-center gap-4 py-2.5 text-left rounded-lg hover:bg-[#F6F8FB] group",children:[w,e.jsx(ge,{className:"w-3.5 h-3.5 text-[#CBD5E1] group-hover:text-[#DC3545]"})]}):e.jsx("div",{className:"flex items-center gap-4 py-2.5",children:w})},h.date+h.title)}),p.length===0&&e.jsxs("li",{className:"py-8 text-center text-xs text-[#64748B]",children:["Nothing scheduled ",s==="week"?"this week":"later","."]})]},s)]})},oc={"finance-staff":{icon:Mt,bg:"#EAF6EC",fg:"#15803D"},"examination-staff":{icon:Qe,bg:"#EEEEFD",fg:"#4338CA"},"org-admin":{icon:He,bg:"#F3EEFF",fg:"#6D28D9"},"super-admin":{icon:He,bg:"#F3EEFF",fg:"#6D28D9"},"department-admin":{icon:Ue,bg:"#FFF1E6",fg:"#C2410C"},coach:{icon:Ue,bg:"#FFF1E6",fg:"#C2410C"},"support-staff":{icon:bt,bg:"#E8F4FD",fg:"#0369A1"},faculty:{icon:Lt,bg:"#EAF1FF",fg:"#1D4ED8"},governance:{icon:It,bg:"#FDECEC",fg:"#C2353F"},facility:{icon:Oe,bg:"#ECFAF8",fg:"#0F766E"},system:{icon:zi,bg:"#F1F5F9",fg:"#475569"}},lc=t=>oc[t],dc={Success:{cls:"bg-[#EEF7F1] text-[#126B3D] ring-[#CDE8D8]",icon:z},Warning:{cls:"bg-[#FEF3E2] text-[#8A4F00] ring-[#FBE3BD]",icon:Ye},Failed:{cls:"bg-[#FEF2F2] text-[#B91C1C] ring-[#FECACA]",icon:es}},Ts=({items:t,subtitle:n="Sample events",action:s})=>e.jsxs("section",{className:H,children:[e.jsx(G,{title:e.jsxs("span",{className:"inline-flex items-center gap-2.5",children:[e.jsx("span",{className:"w-7 h-7 rounded-lg bg-[var(--accent-tint)] text-[var(--accent)] flex items-center justify-center",children:e.jsx(Et,{className:"w-4 h-4"})}),"Recent Activity",e.jsx("span",{className:"inline-flex items-center gap-1.5 rounded-full bg-[#F1F5F9] px-2 py-0.5 text-[10.5px] font-semibold text-[#475569]",children:"Sample"})]}),subtitle:n,action:s}),e.jsx("ul",{className:"relative px-3 pb-3",children:t.map((a,i)=>{const o=a.tone??{icon:Et,bg:"var(--accent-tint)",fg:"var(--accent)"},m=o.icon,p=dc[a.status],h=p.icon,u=i===t.length-1;return e.jsxs("li",{className:"group relative flex items-center gap-4 rounded-lg px-2 py-2.5 transition-all duration-200 hover:bg-[#F8FAFC] hover:translate-x-0.5 animate-fade-up",style:{animationDelay:`${120+i*70}ms`},children:[e.jsx("span",{className:"hidden sm:block w-20 flex-shrink-0 text-right text-[12px] font-medium text-[#64748B] tabular-nums",children:a.time}),e.jsxs("span",{className:"relative flex-shrink-0 self-stretch flex items-center",children:[!u&&e.jsx("span",{"aria-hidden":!0,className:"absolute left-1/2 top-1/2 h-[calc(100%+20px)] w-px -translate-x-1/2 bg-[#E6EAF0]"}),e.jsx("span",{className:"relative z-10 w-8 h-8 rounded-full ring-4 ring-white flex items-center justify-center transition-transform duration-200 group-hover:scale-110",style:{backgroundColor:o.bg,color:o.fg},children:e.jsx(m,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsx("p",{className:"text-[13.5px] font-medium text-[#12233F] truncate",children:a.title}),e.jsx("p",{className:"text-xs text-[#64748B] truncate",children:a.meta})]}),e.jsxs("span",{className:`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-md ring-1 flex-shrink-0 ${p.cls}`,children:[e.jsx(h,{className:"w-3.5 h-3.5"}),a.status]})]},a.id)})})]}),cc=[{key:"academics",name:"Academic"},{key:"sportsQuota",name:"Sports quota"}],le={admissions:{fg:"#7E22CE",bg:"#F3E8FF"},exams:{fg:"#4338CA",bg:"#EEEEFD"},workflow:{fg:"#6256C9",bg:"#EFEDFB"},finance:{fg:"#15803D",bg:"#EAF6EC"},governance:{fg:"#DC2626",bg:"#FEF2F2"},sports:{fg:"#C2410C",bg:"#FFF1E6"}},mc=[{inDays:1,title:"Admission review",meta:"Admissions committee · Batch 2026",category:"Admissions",tone:le.admissions,to:"/admissions"},{inDays:5,title:"Examination schedule",meta:"End-semester timetable release",category:"Exam",tone:le.exams,to:"/modules/examinations"},{inDays:8,title:"Finance reconciliation",meta:"Autumn fee ledger close",category:"Finance",tone:le.finance,to:"/modules/fees-accounts"},{inDays:12,title:"Inter-university athletics",meta:"Tournament & events · Main campus",category:"Sports",tone:le.sports,to:"/modules/tournament-events"}],pc=t=>{const n=new Date;return n.setDate(n.getDate()+t),`${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,"0")}-${String(n.getDate()).padStart(2,"0")}`},Nt=({children:t})=>e.jsxs("span",{className:"inline-flex items-center",children:[e.jsx(Qn,{className:"w-3 h-3 mr-0.5"}),t]}),uc=t=>t<12?"Good morning":t<17?"Good afternoon":"Good evening",hc=()=>{const t=Ht(),{session:n}=ie(),s=(n==null?void 0:n.me.name)||(n==null?void 0:n.me.email)||"Administrator",a=xt(),[i,o]=f.useState(null),[m,p]=f.useState(0),[h,u]=f.useState(!1),v=f.useRef(null);f.useEffect(()=>{const b=S=>{v.current&&!v.current.contains(S.target)&&u(!1)};return document.addEventListener("mousedown",b),()=>document.removeEventListener("mousedown",b)},[]);const g=b=>{o(b),setTimeout(()=>o(null),3e3)},l=[{label:"Generate report",icon:Qi,run:()=>g("Reports need platform/reporting, which is not built yet")},{label:"Create user",icon:vr,run:()=>a("/users?new=1")},{label:"New announcement",icon:lr,run:()=>g("Announcements need platform/notification, which is not built yet")},{label:"Refresh metrics",icon:gr,run:()=>{p(b=>b+1),g("Sample figures reloaded")}}],x=[{label:"Total Students",icon:Je,value:e.jsx(ke,{end:3842},m),delta:e.jsx(Nt,{children:"+4.8%"}),note:"vs last session",to:"/modules/student-information",viz:e.jsx(Cd,{values:[3420,3510,3560,3640,3700,3790,3842],colors:["#6256C9","#315EA8","#159A72","#22A06B","#E89A35","#E45B67","#315EA8"]})},{label:"Active Athletes",icon:Ue,value:e.jsx(ke,{end:428},m),delta:e.jsx(Nt,{children:"+8.2%"}),note:"16 disciplines",to:"/modules/athlete-performance",viz:e.jsx(Md,{delay:600,slices:[{value:30,color:"#315EA8"},{value:20,color:"#159A72"},{value:18,color:"#E89A35"},{value:14,color:"#E45B67"},{value:18,color:"#6256C9"}]})},{label:"Pending Approvals",icon:sn,value:e.jsx(ke,{end:38},m),delta:"12 urgent",deltaTone:"alert",to:"/admissions",viz:e.jsx(Dd,{delay:300,bars:[{value:12,color:"#E45B67"},{value:10,color:"#6256C9"},{value:8,color:"#E89A35"},{value:5,color:"#315EA8"},{value:3,color:"#159A72"}]})},{label:"Fee Collection",icon:Mt,value:e.jsx(ke,{end:8.42,decimals:2,prefix:"₹",suffix:" Cr"},m),delta:e.jsx(Nt,{children:"+12.4%"}),note:"Autumn 2026",to:"/modules/fees-accounts",viz:e.jsx(Rd,{delay:900,colors:["#22A06B","#315EA8","#E89A35"],stacks:[[3.1,1.3,.7],[3.4,1.4,.8],[3.7,1.6,.9],[4,1.7,.9],[4.4,1.8,1.1],[4.7,2,1.2],[5,2.1,1.32]]})},{label:"Active Faculty",icon:zn,value:e.jsx(ke,{end:312},m),delta:"96% rostered",deltaTone:"muted",accent:"navy",to:"/modules/hr-payroll",viz:e.jsx(Pd,{of:100,delay:450,slices:[{value:34,color:"#6256C9"},{value:26,color:"#315EA8"},{value:21,color:"#159A72"},{value:15,color:"#E89A35"}]})},{label:"Support Tickets",icon:bt,value:e.jsx(ke,{end:24},m),delta:"Avg response 4.2h",deltaTone:"muted",accent:"orange",to:"/modules/helpdesk",viz:e.jsx(Od,{delay:1200,value:4.2/6,zones:[{to:.5,color:"#22A06B"},{to:.8333,color:"#E89A35"},{to:1,color:"#E45B67"}]})}],w=[{label:"Admission approvals",count:12,level:"urgent",icon:qe,tone:le.admissions,onOpen:()=>a("/admissions")},{label:"Other approvals",count:10,level:"pending",icon:sn,tone:le.workflow,onOpen:()=>a("/modules/workflow")},{label:"Examination approvals",count:8,level:"pending",icon:Qe,tone:le.exams,onOpen:()=>a("/modules/examinations")},{label:"Finance approvals",count:5,level:"pending",icon:Mt,tone:le.finance,onOpen:()=>a("/modules/fees-accounts")},{label:"Grievance cases",count:3,level:"normal",icon:It,tone:le.governance,onOpen:()=>a("/modules/grievance")}],N=mc.map(({inDays:b,to:S,...E})=>({...E,date:pc(b),onOpen:()=>a(S)}));return e.jsxs("div",{className:"space-y-6",children:[i&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs",children:[e.jsx(z,{className:"w-4 h-4 text-[#6FCF97]"}),e.jsx("span",{children:i})]}),e.jsx(me,{title:"Dashboard",art:e.jsx(Gt,{}),subtitle:e.jsxs(e.Fragment,{children:[e.jsxs("span",{className:"block text-[15px] text-[#12233F]",children:[uc(new Date().getHours()),", ",e.jsx("span",{className:"font-semibold",children:s})]}),e.jsxs("span",{className:"block mt-0.5 text-[13px] text-[#64748B]",children:[t.name," · Academic Year 2026–27"]})]}),actions:e.jsxs(e.Fragment,{children:[e.jsxs("button",{onClick:()=>g("Student records need the student-information module, which is not built yet"),className:se,children:[e.jsx(wr,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),"Add Student"]}),e.jsxs("button",{onClick:()=>a("/admissions"),className:Fe,children:[e.jsx(qe,{className:"w-3.5 h-3.5"}),"Review Admissions"]}),e.jsxs("div",{className:"relative",ref:v,children:[e.jsxs("button",{onClick:()=>u(b=>!b),"aria-haspopup":"menu","aria-expanded":h,className:se,children:["More",e.jsx(ze,{className:"w-3.5 h-3.5 text-[#64748B]"})]}),h&&e.jsx("div",{role:"menu",className:"absolute right-0 mt-1.5 w-48 rounded-lg bg-white border border-[#E2E8F0] shadow-lg py-1 z-20",children:l.map(({label:b,icon:S,run:E})=>e.jsxs("button",{role:"menuitem",onClick:()=>{u(!1),E()},className:"w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#12233F] hover:bg-[#F6F8FB]",children:[e.jsx(S,{className:"w-3.5 h-3.5 text-[#64748B]"}),b]},b))})]})]})}),e.jsx(ce,{stats:x,colorful:!0}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsx(zt,{className:"lg:col-span-2 eos-lift",title:"Student Enrollment",subtitle:"Enrollment by academic year",data:fd,xKey:"year",series:cc,height:260,tooltipLabel:b=>`Academic year ${b}`}),e.jsx(Kt,{className:"eos-lift",title:"Admissions Overview",subtitle:"Batch 2026",relativeToFirst:!0,items:ms.map((b,S)=>({label:b.stage,count:b.count,color:cs[S]})),action:e.jsx(kn,{onClick:()=>a("/admissions"),children:"View Admissions"}),footer:{label:"Overall acceptance",value:"37.8%"}})]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-2 gap-6",children:[e.jsx(nc,{rows:w,className:"eos-lift"}),e.jsx(rc,{items:N,className:"eos-lift"})]}),e.jsx(Ts,{items:ds.slice(0,5).map(b=>({id:b.id,time:b.timestamp,title:b.action,meta:`${b.user} · ${J(b.role)}`,status:b.status,tone:lc(b.role)})),action:e.jsx(kn,{onClick:()=>a("/audit-logs"),children:"View all"})})]})},gc=t=>{var n;return{id:t.id,name:t.name,email:t.email,role:t.roles[0]??"student",department:"–",status:"Active",lastLogin:"–",dataScope:((n=pt(t.roles[0]??""))==null?void 0:n.dataScope)??"Self"}},fc=()=>{var q;const{session:t}=ie(),{ROLES:n}=Ut(),s=!!(t!=null&&t.organisation),a=!(t!=null&&t.me.is_super_admin),[i]=On(),[o,m]=f.useState(s?[]:hd),[p,h]=f.useState(""),[u,v]=f.useState(!1),g=f.useCallback(async()=>{if(s)try{m((await Jt("/identity/users")).map(gc))}catch(A){R(A instanceof _t?`Could not load users: ${A.message}`:"Could not load users")}},[s]);f.useEffect(()=>{g()},[g]);const[l,x]=f.useState(""),[w,N]=f.useState("All"),[b,S]=f.useState("All"),[E,y]=f.useState("All"),[k,B]=f.useState(null),[T,C]=f.useState(!1),[M,j]=f.useState(!1);f.useEffect(()=>{i.get("new")==="1"&&a&&j(!0)},[i,a]);const[P,R]=f.useState(null),[_,D]=f.useState(""),[I,pe]=f.useState(""),[Z,X]=f.useState("faculty"),[V,ee]=f.useState("Physical Education"),te=A=>{R(A),setTimeout(()=>R(null),3e3)},re=A=>{B(A),C(!0)},_e=()=>{C(!1),B(null)},Se=A=>{m(ne=>ne.map(Q=>{if(Q.id===A){const be=Q.status==="Active"?"Suspended":"Active",tt={...Q,status:be};return(k==null?void 0:k.id)===A&&B(tt),te(`Preview only: ${Q.name} shown as ${be}; suspending users is not in the identity API yet`),tt}return Q}))},Be=async A=>{var Q;if(A.preventDefault(),!_||!I)return;if(s){v(!0);try{await Jt("/identity/users",{method:"POST",json:{email:I,name:_,password:p,roles:[Z]}}),await g(),j(!1),D(""),pe(""),h(""),te(`${_} can now sign in with ${I}`)}catch(be){te(be instanceof _t?`Not created: ${be.message}`:"Not created")}finally{v(!1)}return}const ne={id:`USR-${1e3+o.length+1}`,name:_,email:I,role:Z,department:V,status:"Active",lastLogin:"Never (New)",dataScope:((Q=pt(Z))==null?void 0:Q.dataScope)??"Department"};m([ne,...o]),j(!1),D(""),pe(""),h(""),te(`Preview only: ${ne.name} added to this page, not saved`)},xe=o.filter(A=>{const ne=A.name.toLowerCase().includes(l.toLowerCase())||A.email.toLowerCase().includes(l.toLowerCase())||A.id.toLowerCase().includes(l.toLowerCase()),Q=w==="All"||A.role===w,be=b==="All"||A.department===b,tt=E==="All"||A.status===E;return ne&&Q&&be&&tt}),Ae=["All",...Array.from(new Set(o.map(A=>A.role)))],L=["All",...Array.from(new Set(o.map(A=>A.department)))];return e.jsxs("div",{className:"space-y-6",children:[P&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs",children:[e.jsx(z,{className:"w-4 h-4 text-[#126B3D]"}),e.jsx("span",{children:P})]}),e.jsx(me,{title:"Users & Access",subtitle:s?"Users of your organisation, from platform/identity.":t!=null&&t.me.is_super_admin?"Sample directory. Users belong to organisations; a super admin works through organisation screens (not built yet).":"Sample directory (preview). Sign in as an organisation admin to see and add real users.",actions:a?e.jsxs("button",{onClick:()=>j(!0),className:Fe,children:[e.jsx(Yn,{className:"w-3.5 h-3.5"}),"Add User"]}):void 0}),e.jsx(ce,{stats:[{label:"Users",icon:Je,value:o.length.toLocaleString("en-IN"),note:s?"In your organisation":"Sample list"},{label:"Active",icon:Xn,value:String(o.filter(A=>A.status==="Active").length),note:s?"Can sign in":"Sample list"},{label:"Pending",icon:Ke,value:String(o.filter(A=>A.status==="Pending").length),note:"Not signed in yet"},{label:"Suspended",icon:kr,value:String(o.filter(A=>A.status==="Suspended").length),deltaTone:"alert",note:"Sample only: no suspend API yet"}]}),e.jsx("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs space-y-3",children:e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3",children:[e.jsxs("div",{className:"relative",children:[e.jsx(he,{className:"w-4 h-4 text-[#475569] absolute left-3 top-2.5"}),e.jsx("input",{type:"text",placeholder:"Search by name, ID or email...",value:l,onChange:A=>x(A.target.value),className:"w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"})]}),e.jsx("div",{children:e.jsxs("select",{value:w,onChange:A=>N(A.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Roles"}),Ae.filter(A=>A!=="All").map(A=>e.jsx("option",{value:A,children:J(A)},A))]})}),e.jsx("div",{children:e.jsxs("select",{value:b,onChange:A=>S(A.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Departments"}),L.filter(A=>A!=="All").map(A=>e.jsx("option",{value:A,children:A},A))]})}),e.jsx("div",{children:e.jsxs("select",{value:E,onChange:A=>y(A.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Statuses"}),e.jsx("option",{value:"Active",children:"Active"}),e.jsx("option",{value:"Pending",children:"Pending"}),e.jsx("option",{value:"Suspended",children:"Suspended"})]})})]})}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden",children:[e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-3 px-4",children:"User ID"}),e.jsx("th",{className:"py-3 px-4",children:"Name"}),e.jsx("th",{className:"py-3 px-4",children:"Role"}),e.jsx("th",{className:"py-3 px-4",children:"Department"}),e.jsx("th",{className:"py-3 px-4",children:"Email"}),e.jsx("th",{className:"py-3 px-4",children:"Status"}),e.jsx("th",{className:"py-3 px-4",children:"Last Login"}),e.jsx("th",{className:"py-3 px-4 text-right",children:"Actions"})]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9] text-[#12233F]",children:xe.length===0?e.jsx("tr",{children:e.jsx("td",{colSpan:8,className:"py-8 text-center text-[#475569]",children:"No university users match the applied filters."})}):xe.map(A=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors cursor-pointer group",onClick:()=>re(A),children:[e.jsx("td",{className:"py-3 px-4 font-mono font-medium text-[#7E22CE]",children:A.id}),e.jsxs("td",{className:"py-3 px-4",children:[e.jsx("div",{className:"font-semibold text-[#12233F]",children:A.name}),e.jsx("div",{className:"text-[11px] text-[#64748B] font-mono",children:A.employeeId})]}),e.jsx("td",{className:"py-3 px-4",children:e.jsx("span",{className:"inline-flex items-center gap-1 font-medium px-2 py-0.5 rounded bg-[#F1F5F9] text-[#7E22CE]",children:J(A.role)})}),e.jsx("td",{className:"py-3 px-4 text-[#475569]",children:A.department}),e.jsx("td",{className:"py-3 px-4 text-[#475569] font-mono text-[11px]",children:A.email}),e.jsx("td",{className:"py-3 px-4",children:e.jsxs("span",{className:`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${A.status==="Active"?"bg-[#16834B26] text-[#126B3D]":A.status==="Pending"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-current"}),A.status]})}),e.jsx("td",{className:"py-3 px-4 text-[#475569] whitespace-nowrap",children:A.lastLogin}),e.jsx("td",{className:"py-3 px-4 text-right",onClick:ne=>ne.stopPropagation(),children:e.jsx("button",{onClick:()=>re(A),className:"px-2.5 py-1 rounded border border-[#E2E8F0] hover:border-[#9333EA] text-[#7E22CE] font-medium hover:bg-[#FFFFFF] text-[11px] transition-colors",children:"Details →"})})]},A.id))})]})}),e.jsxs("div",{className:"py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]",children:[e.jsxs("span",{children:["Showing ",e.jsx("strong",{className:"text-[#12233F]",children:xe.length})," of"," ",e.jsx("strong",{className:"text-[#12233F]",children:o.length})," loaded staff records"]}),e.jsx("span",{className:"text-[11px]",children:"Sample data · identity lists and creates users today"})]})]}),T&&k&&e.jsxs("div",{className:"fixed inset-0 z-50 overflow-hidden",children:[e.jsx("div",{className:"absolute inset-0 bg-[#12233F]/50 backdrop-blur-xs transition-opacity",onClick:_e}),e.jsx("div",{className:"fixed inset-y-0 right-0 max-w-full flex pl-10",children:e.jsxs("div",{className:"w-screen max-w-md bg-[#FFFFFF] shadow-2xl border-l border-[#E2E8F0] flex flex-col",children:[e.jsxs("div",{className:"p-5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]",children:[e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx("span",{className:"font-mono text-xs px-2 py-0.5 rounded bg-[#7E22CE26] text-[#7E22CE] font-semibold",children:k.id}),e.jsx("span",{className:"text-sm font-bold text-[#12233F]",children:"User Profile & Scope"})]}),e.jsx("button",{onClick:_e,className:"p-1 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#FFFFFF]",children:e.jsx(ae,{className:"w-5 h-5"})})]}),e.jsxs("div",{className:"flex-1 overflow-y-auto p-6 space-y-6",children:[e.jsxs("div",{className:"flex items-center gap-4 pb-4 border-b border-[#F1F5F9]",children:[e.jsx("div",{className:"w-14 h-14 rounded-xl bg-[#7E22CE] text-white flex items-center justify-center font-bold text-lg shadow-sm",children:k.name.split(" ").map(A=>A[0]).slice(0,2).join("")}),e.jsxs("div",{children:[e.jsx("h3",{className:"text-base font-bold text-[#12233F]",children:k.name}),e.jsx("p",{className:"text-xs text-[#7E22CE] font-medium",children:J(k.role)}),e.jsxs("p",{className:"text-[10px] text-[#64748B] font-mono",children:["role: ",k.role," · ",((q=pt(k.role))==null?void 0:q.permissions.length)??0," permission keys"]}),e.jsx("p",{className:"text-[11px] text-[#475569]",children:k.department})]})]}),e.jsxs("div",{className:"space-y-3",children:[e.jsx("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]",children:"Institutional Details"}),e.jsxs("div",{className:"p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2.5 text-xs",children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Employee Code:"}),e.jsx("span",{className:"font-mono font-medium text-[#12233F]",children:k.employeeId})]}),e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Institutional Email:"}),e.jsx("span",{className:"font-mono text-[#7E22CE]",children:k.email})]}),e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Official Phone:"}),e.jsx("span",{className:"text-[#12233F]",children:k.phone})]}),e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Last Authenticated:"}),e.jsx("span",{className:"text-[#12233F]",children:k.lastLogin})]})]})]}),e.jsxs("div",{className:"space-y-2",children:[e.jsx("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]",children:"Data Scope (sample, not enforced)"}),e.jsxs("div",{className:"p-3.5 rounded-lg bg-[#7E22CE26]/50 border border-[#9333EA]/20 flex items-start gap-3",children:[e.jsx(de,{className:"w-4 h-4 text-[#7E22CE] mt-0.5"}),e.jsxs("div",{children:[e.jsxs("div",{className:"font-semibold text-xs text-[#7E22CE]",children:[k.dataScope," Scope"]}),e.jsx("p",{className:"text-[11px] text-[#475569] mt-0.5",children:k.dataScope==="Institution"?"Whole organisation. Row-level security today is per organisation only.":k.dataScope==="Department"?`Own department (${k.department}). Not enforced by the API yet.`:"Assigned records only. Not enforced by the API yet."})]})]})]}),e.jsxs("div",{className:"space-y-2",children:[e.jsx("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]",children:"Security Status"}),e.jsxs("div",{className:"p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2 text-xs",children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Two-Factor Authentication:"}),e.jsx("span",{className:"font-semibold px-2 py-0.5 rounded text-[10px] bg-[#F1F5F9] text-[#475569]",children:"Not available yet"})]}),e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("span",{className:"text-[#475569]",children:"Account Status:"}),e.jsx("span",{className:`font-semibold px-2 py-0.5 rounded text-[10px] ${k.status==="Active"?"bg-[#16834B26] text-[#126B3D]":k.status==="Pending"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:k.status})]})]})]})]}),e.jsx("div",{className:"p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] space-y-2",children:e.jsxs("div",{className:"grid grid-cols-2 gap-2",children:[e.jsx("button",{onClick:()=>{te("Password reset is not in the identity API yet")},className:"py-2 px-3 rounded-lg border border-[#E2E8F0] hover:bg-[#FFFFFF] text-xs font-medium text-[#12233F] transition-colors",children:"Reset Password"}),e.jsx("button",{onClick:()=>Se(k.id),className:`py-2 px-3 rounded-lg text-xs font-medium transition-colors ${k.status==="Active"?"border border-[#DC262626] text-[#B91C1C] hover:bg-[#DC262626]/30":"border border-[#16834B26] text-[#126B3D] hover:bg-[#16834B26]/50"}`,children:k.status==="Active"?"Suspend User":"Activate User"})]})})]})})]}),M&&e.jsx("div",{className:"fixed inset-0 z-50 bg-[#12233F]/40 backdrop-blur-xs flex items-center justify-center p-4",children:e.jsxs("div",{className:"w-full max-w-md bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden",children:[e.jsxs("div",{className:"p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]",children:[e.jsx("h3",{className:"text-sm font-bold text-[#12233F]",children:"Create Institutional User"}),e.jsx("button",{onClick:()=>j(!1),className:"text-[#475569] hover:text-[#12233F]",children:e.jsx(ae,{className:"w-4 h-4"})})]}),e.jsxs("form",{onSubmit:Be,className:"p-5 space-y-4 text-xs",children:[e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Full Name"}),e.jsx("input",{type:"text",required:!0,value:_,onChange:A=>D(A.target.value),placeholder:"e.g. Gurpreet Singh",className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"})]}),e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Institutional Email"}),e.jsx("input",{type:"email",required:!0,value:I,onChange:A=>pe(A.target.value),placeholder:"e.g. name@your-institution.edu",className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"})]}),e.jsxs("div",{className:"grid grid-cols-2 gap-3",children:[e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Assigned Role"}),e.jsx("select",{value:Z,onChange:A=>X(A.target.value),className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]",children:n.filter(A=>A.id!=="super-admin").map(A=>e.jsx("option",{value:A.id,children:A.title},A.id))})]}),e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Department"}),e.jsxs("select",{value:V,onChange:A=>ee(A.target.value),className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]",children:[e.jsx("option",{value:"Sports Science & Biomechanics",children:"Sports Science"}),e.jsx("option",{value:"Athletics & Track",children:"Athletics"}),e.jsx("option",{value:"Physical Education",children:"Physical Education"}),e.jsx("option",{value:"Finance & Accounts",children:"Finance"}),e.jsx("option",{value:"Computer Science & AI",children:"Computer Science"})]})]})]}),e.jsxs("div",{children:[e.jsx("label",{className:"block font-semibold text-[#12233F] mb-1",children:"Initial Password"}),e.jsx("input",{type:"password",required:!0,minLength:8,value:p,onChange:A=>h(A.target.value),placeholder:"At least 8 characters",className:"w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"})]}),e.jsx("div",{className:"p-3 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[11px] text-[#475569]",children:s?"Created in your organisation through platform/identity. Share the password with the user; email invitations and 2FA are not available yet.":"Preview: the user is added to this page only and not saved."}),e.jsxs("div",{className:"flex justify-end gap-2 pt-2",children:[e.jsx("button",{type:"button",onClick:()=>j(!1),className:"px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569]",children:"Cancel"}),e.jsx("button",{type:"submit",disabled:u,className:"px-4 py-1.5 rounded-lg bg-[#F65B66] text-white font-semibold hover:bg-[#E9505C]",children:u?"Creating…":"Create User"})]})]})]})})]})},yc=[...fe.map(t=>({id:t.id,label:vt(t),color:t.color,modules:t.modules})),{id:"platform",label:"Platform services",color:"#9333EA",modules:Ce},{id:"integrations",label:"Integrations",color:"#16834B",modules:Te}],it=t=>(Xe[t.id]??[]).map(n=>n.key),xc=[{id:"Institution",hint:"Entire organisation"},{id:"Department",hint:"Own department"},{id:"Assigned Records",hint:"Assigned classes / athletes"},{id:"Self",hint:"Own records only"}],bc=()=>{const{ROLES:t,ROLE_LAYOUTS:n,ROLES_SOURCE:s}=Ut(),[a,i]=f.useState(()=>t.map(C=>({...C,permissions:[...C.permissions]}))),[o,m]=f.useState("department-admin"),[p,h]=f.useState(""),[u,v]=f.useState(!1),[g,l]=f.useState({}),[x,w]=f.useState(null),N=a.find(C=>C.id===o)??a[0],b=f.useMemo(()=>new Set(N.permissions),[N]),S=n[N.id],E=C=>{w(C),setTimeout(()=>w(null),3e3)},y=C=>i(M=>M.map(j=>j.id===o?C(j):j)),k=C=>{y(M=>({...M,dataScope:C})),E(`Sample setting: "${C}" is shown for ${N.title} but is not stored or enforced`)},B=p.trim().toLowerCase(),T=yc.map(C=>({...C,modules:C.modules.filter(M=>!(B&&!M.name.toLowerCase().includes(B)&&!M.id.includes(B)||u&&!it(M).some(j=>b.has(j))))})).filter(C=>C.modules.length>0);return e.jsxs("div",{className:"space-y-6",children:[x&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs",children:[e.jsx(z,{className:"w-4 h-4 text-[#126B3D]"}),e.jsx("span",{children:x})]}),e.jsx(me,{title:"Roles & Permissions",subtitle:e.jsxs(e.Fragment,{children:["Roles from the academy profile plus the platform roles. Modules check permission keys"," ",e.jsx("code",{className:"text-[#6B21A8]",children:"<module>:<resource>:<action>"}),", granted to roles in each module's contracts/permissions.yaml."]})}),e.jsx(ce,{stats:[{label:"Roles",icon:de,value:String(a.length),note:`${a.filter(C=>!C.system).length} from the profile + org-admin, super-admin`},{label:"Assigned users",icon:Je,value:a.reduce((C,M)=>C+M.userCount,0).toLocaleString("en-IN"),note:"Across all roles"},{label:"Keys for this role",icon:Ne,value:String(N.permissions.length),note:N.title},{label:"Dashboard layouts",icon:Me,value:String(Object.keys(n).length),note:"platform/identity/config/dashboards"}]}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs",children:[e.jsxs("div",{className:"text-[11px] font-bold uppercase tracking-wider text-[#475569] mb-3 flex items-center gap-1.5",children:[e.jsx(de,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),e.jsx("span",{children:"How access is decided (platform/identity)"})]}),e.jsx("div",{className:"grid grid-cols-2 md:grid-cols-5 gap-2",children:[{step:"1. User",sub:"Email and password (platform/identity)"},{step:"2. Role",sub:"From the academy profile, or a platform role"},{step:"3. Permission keys",sub:"Modules check keys, never roles"},{step:"4. Organisation",sub:"Row-level security on organisation_id"},{step:"5. Entitlement",sub:"Module must be in profile and plan"}].map((C,M)=>e.jsxs("div",{className:"flex items-center justify-between p-2.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0]",children:[e.jsxs("div",{className:"min-w-0",children:[e.jsx("div",{className:"text-xs font-bold text-[#7E22CE]",children:C.step}),e.jsx("div",{className:"text-[10px] text-[#475569] truncate",children:C.sub})]}),M<4&&e.jsx(ge,{className:"hidden md:block w-3.5 h-3.5 text-[#64748B] flex-shrink-0"})]},C.step))})]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-12 gap-6 items-start",children:[e.jsxs("div",{className:"lg:col-span-4 bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs space-y-3 lg:sticky lg:top-20",children:[e.jsxs("div",{className:"flex items-center justify-between pb-2 border-b border-[#E2E8F0]",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F]",children:["Roles (",a.length,")"]}),e.jsx("span",{className:"text-[11px] text-[#64748B] truncate",title:s,children:s.replace("platform/identity/config/","")})]}),e.jsx("div",{className:"space-y-1 max-h-[60vh] overflow-y-auto pr-1",children:a.map(C=>{const M=C.id===o;return e.jsxs("button",{onClick:()=>m(C.id),className:`w-full text-left px-3 py-2.5 rounded-lg transition-all border ${M?"bg-[#7E22CE26] border-[#9333EA] shadow-xs":"border-transparent hover:bg-[#F6F8FB]"}`,children:[e.jsxs("div",{className:"flex items-center justify-between gap-2",children:[e.jsx("span",{className:`text-xs font-bold truncate ${M?"text-[#7E22CE]":"text-[#12233F]"}`,children:C.title}),C.system&&e.jsx("span",{className:"text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded bg-[#F39A1926] text-[#8A4F00] flex-shrink-0",children:"system"})]}),e.jsxs("div",{className:"mt-1 flex items-center gap-2 text-[10px] text-[#475569]",children:[e.jsx("span",{className:"font-mono text-[#64748B]",children:C.id}),e.jsx("span",{children:"•"}),e.jsxs("span",{children:[C.userCount.toLocaleString("en-IN")," users"]}),e.jsx("span",{children:"•"}),e.jsxs("span",{children:[C.permissions.length," keys"]})]})]},C.id)})})]}),e.jsxs("div",{className:"lg:col-span-8 space-y-6",children:[e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-5 shadow-2xs space-y-4",children:[e.jsxs("div",{className:"flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-3 border-b border-[#E2E8F0]",children:[e.jsxs("div",{children:[e.jsxs("div",{className:"flex items-center gap-2 flex-wrap",children:[e.jsx("h2",{className:"text-lg font-bold text-[#12233F]",children:N.title}),e.jsx("span",{className:"text-xs font-mono px-2 py-0.5 rounded bg-[#F1F5F9] text-[#475569]",children:N.id})]}),e.jsx("p",{className:"text-xs text-[#475569] mt-1 max-w-2xl",children:N.description})]}),e.jsxs("span",{className:"text-xs font-medium px-2.5 py-1 rounded bg-[#16834B26] text-[#126B3D] self-start whitespace-nowrap",children:[N.userCount.toLocaleString("en-IN")," users"]})]}),e.jsxs("div",{children:[e.jsxs("div",{className:"flex items-center justify-between mb-2",children:[e.jsx("label",{className:"text-xs font-bold uppercase tracking-wider text-[#12233F]",children:"Data scope"}),e.jsx("span",{className:"text-[11px] text-[#475569]",children:"Sample setting, not in the repo yet; row-level security is per organisation"})]}),e.jsx("div",{className:"grid grid-cols-2 sm:grid-cols-4 gap-2",children:xc.map(({id:C,hint:M})=>{const j=N.dataScope===C;return e.jsxs("button",{onClick:()=>k(C),className:`p-2.5 rounded-lg border text-left transition-all ${j?"border-[#9333EA] bg-[#7E22CE26] text-[#7E22CE] font-bold shadow-2xs":"border-[#E2E8F0] hover:bg-[#F6F8FB] text-[#475569]"}`,children:[e.jsxs("div",{className:"text-xs flex items-center justify-between",children:[e.jsx("span",{children:C}),j&&e.jsx(Ve,{className:"w-3.5 h-3.5"})]}),e.jsx("span",{className:"text-[10px] font-normal block mt-0.5 text-[#475569]",children:M})]},C)})})]}),e.jsxs("div",{className:"pt-3 border-t border-[#E2E8F0]",children:[e.jsxs("div",{className:"flex items-center justify-between mb-2",children:[e.jsxs("label",{className:"text-xs font-bold uppercase tracking-wider text-[#12233F] flex items-center gap-1.5",children:[e.jsx(Me,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),"Dashboard layout"]}),S&&e.jsx(W,{to:`/dashboards?role=${N.id}`,className:"text-[11px] text-[#7E22CE] hover:underline",children:"Preview dashboard →"})]}),S?e.jsxs(e.Fragment,{children:[e.jsxs("p",{className:"text-[11px] text-[#64748B] mb-2 font-mono",children:["platform/identity/config/dashboards/",S.role,".yaml",S.extends&&e.jsxs("span",{className:"text-[#475569]",children:[" · extends ",S.extends]})]}),e.jsx("div",{className:"flex flex-wrap gap-1.5",children:Pe(N.id).map(C=>e.jsx("span",{className:"text-[10px] font-mono px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155]",children:C},C))})]}):e.jsx("p",{className:"text-[11px] text-[#475569]",children:"No dashboard layout. System roles use the admin console."})]})]}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden",children:[e.jsxs("div",{className:"p-4 border-b border-[#E2E8F0] bg-[#F6F8FB] flex flex-col md:flex-row md:items-center justify-between gap-3",children:[e.jsxs("div",{children:[e.jsxs("h3",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5",children:[e.jsx(Ne,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),"Permission keys · ",N.title]}),e.jsx("p",{className:"text-[11px] text-[#475569]",children:"Each chip is a key a module defines in its contracts/permissions.yaml. Grants are made there, by role name."})]}),e.jsxs("div",{className:"flex items-center gap-2 flex-wrap",children:[e.jsxs("div",{className:"relative",children:[e.jsx(he,{className:"w-3.5 h-3.5 text-[#64748B] absolute left-2.5 top-1/2 -translate-y-1/2"}),e.jsx("input",{value:p,onChange:C=>h(C.target.value),placeholder:"Filter modules",className:"pl-8 pr-3 py-1.5 w-40 rounded-lg bg-[#FFFFFF] border border-[#E2E8F0] text-xs text-[#12233F] placeholder:text-[#64748B] focus:outline-none focus:border-[#9333EA]"})]}),e.jsxs("label",{className:"inline-flex items-center gap-1.5 text-[11px] text-[#334155] cursor-pointer",children:[e.jsx("input",{type:"checkbox",checked:u,onChange:C=>v(C.target.checked),className:"accent-[#7E22CE]"}),"Granted only"]})]})]}),e.jsxs("div",{className:"overflow-x-auto",children:[e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F1F5F9] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-2.5 px-4 min-w-[220px]",children:"Module"}),e.jsx("th",{className:"py-2.5 px-3 uppercase tracking-wider text-[11px]",children:"Permission keys"})]})}),T.map(C=>{const M=g[C.id],j=C.modules.reduce((P,R)=>P+it(R).filter(_=>b.has(_)).length,0);return e.jsxs("tbody",{className:"divide-y divide-[#F1F5F9]",children:[e.jsx("tr",{className:"bg-[#FFFFFF]",children:e.jsx("td",{colSpan:2,className:"py-2 px-4",children:e.jsxs("button",{onClick:()=>l(P=>({...P,[C.id]:!P[C.id]})),className:"flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-[#334155] w-full",children:[M?e.jsx(Vn,{className:"w-3.5 h-3.5"}):e.jsx(ze,{className:"w-3.5 h-3.5"}),e.jsx("span",{className:"w-2 h-2 rounded-full",style:{background:C.color}}),e.jsx("span",{children:C.label}),e.jsxs("span",{className:"ml-auto font-medium normal-case tracking-normal text-[#64748B]",children:[j," granted"]})]})})}),!M&&C.modules.map(P=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors",children:[e.jsxs("td",{className:"py-2 px-4",children:[e.jsx(W,{to:`/modules/${P.id}`,className:"font-semibold text-[#12233F] hover:text-[#7E22CE]",children:P.name}),e.jsx("div",{className:"text-[10px] font-mono text-[#64748B]",children:P.id})]}),e.jsx("td",{className:"py-2 px-3",children:it(P).length===0?e.jsx("span",{className:"text-[11px] text-[#64748B]",children:"None defined yet"}):e.jsx("div",{className:"flex flex-wrap gap-1.5",children:it(P).map(R=>{const _=b.has(R);return e.jsxs("span",{className:`inline-flex items-center gap-1 px-2 py-1 rounded-md font-mono text-[10px] ${_?"bg-[#16834B26] text-[#126B3D] shadow-2xs":"bg-[#F1F5F9] text-[#64748B]"}`,title:`${R}: ${_?"granted":"not granted"} to ${N.id}`,children:[_?e.jsx(Ve,{className:"w-3.5 h-3.5 stroke-[2.5]"}):e.jsx(ae,{className:"w-3.5 h-3.5 stroke-[2]"}),R]},R)})})})]},P.id))]},C.id)})]}),T.length===0&&e.jsx("p",{className:"p-6 text-center text-xs text-[#475569]",children:"No modules match."})]}),e.jsxs("div",{className:"p-3 bg-[#F6F8FB] border-t border-[#E2E8F0] flex items-center justify-between text-[11px] text-[#475569]",children:[e.jsxs("span",{className:"flex items-center gap-1.5",children:[e.jsx("span",{className:"w-2.5 h-2.5 rounded bg-[#16834B26] border border-[#16834B]/30"}),e.jsx("span",{children:"Granted"}),e.jsx("span",{className:"w-2.5 h-2.5 rounded bg-[#F1F5F9] border border-[#CBD5E1] ml-2"}),e.jsx("span",{children:"Not granted"})]}),e.jsxs("span",{children:[N.permissions.length," keys granted"]})]})]})]})]})]})},r=(t,n,s,a,i)=>({label:t,value:n,note:s,delta:a,tone:i}),d=(t,n,s,a,i,o)=>({ref:t,type:n,title:s,description:a,urgency:i,time:o}),c=(t,n,s,a,i)=>({time:t,title:n,who:s,ref:a,status:i}),Is={"web-portal-cms":{action:"Publish Notice",kpis:[r("Page views (30 days)","1.24 L","Public website traffic","+9.4%"),r("Published pages","342","Across 18 sections","+12"),r("Pending approvals","7","Notices awaiting sign-off","2 urgent","alert"),r("Uptime","99.98%","Last 30 days","SLA met")],chart:{title:"Website Traffic",subtitle:"Monthly visitors, desktop vs mobile",series:["Desktop","Mobile"],base:21e3,split:.42},breakdown:{title:"Top Sections",subtitle:"Views in the last 30 days",items:[["Admissions 2026",48210],["Notices & Circulars",26480],["Sports Programmes",19340],["Results",15620],["Tenders",6310]]},actions:[d("CMS-118","Notice","Merit List 2 announcement","Draft by Admissions Cell, needs Registrar approval","Urgent","20 mins ago"),d("CMS-117","Page update","Hostel fee structure 2026–27","Finance revision pending publication","Pending","2 hours ago"),d("CMS-115","Tender","Synthetic track resurfacing tender","Legal vetting complete, ready to publish","Review","Yesterday")],activity:[c("10:12 AM",'Published "Inter-University Athletics Meet" notice',"Web Admin","CMS-116"),c("09:40 AM","Homepage banner rotated","Web Admin","CMS-BNR-22"),c("Yesterday","Broken link report generated","System","CMS-LNK-07","Warning")]},admissions:{action:"Create Admission",kpis:[r("Total applications","1,284","Undergraduate & Masters","+11.2%"),r("Confirmed","486","Tuition fee paid in full","37.8%"),r("Under review","86","Requires Dean review","urgent","alert"),r("Shortlisted","824","Counselling invitations issued","64.2%")],chart:{title:"Applications Received",subtitle:"Monthly, general vs sports quota",series:["General","Sports quota"],base:210,split:.18},breakdown:{title:"Admissions Funnel",subtitle:"Batch 2026 conversion",items:[["Applications",1284],["Shortlisted",824],["Counselling",612],["Confirmed",486]],footer:["Overall acceptance","37.8%"]},actions:[d("ADM-1024","Application","Harpreet Singh — B.Tech CSE (Sports Analytics)","National sports merit certificate unverified","Urgent","45 mins ago"),d("ADM-1027","Application","Navneet Sandhu — M.P.Ed","Sports quota trial result awaited","Pending","3 hours ago"),d("ADM-ML2","Merit list","Merit List 2 publication","Ready for Dean of Admissions sign-off","Review","Yesterday")],activity:[c("10:30 AM","Application ADM-1026 confirmed","Admissions Cell","ADM-1026"),c("09:55 AM","Counselling slot allotted to 42 candidates","Admissions Cell","CNS-0610"),c("Yesterday","Document mismatch flagged","DigiLocker sync","ADM-1028","Warning")]},"student-information":{action:"Add Student",kpis:[r("Enrolled students","3,842","Active academic records","+4.8%"),r("Student-athletes","428","Linked athlete profiles","+8.2%"),r("Profile updates pending","64","Awaiting verification","9 urgent","alert"),r("ID cards issued","3,611","This academic year","94%")],chart:{title:"Student Records Updated",subtitle:"Monthly, by staff vs self-service",series:["Staff","Self-service"],base:900,split:.55},breakdown:{title:"Students by School",subtitle:"Current enrolment",items:[["Sports Sciences",1210],["Physical Education",980],["Management",702],["Computer Science & AI",590],["Humanities",360]]},actions:[d("SIS-2210","Name change","Gurleen Kaur — name correction","Gazette notification attached","Pending","1 hour ago"),d("SIS-2207","Category update","Ravi Kumar — category to SC","Certificate needs verification","Urgent","3 hours ago"),d("SIS-2199","Status","Semester break request","Medical leave for 1 semester","Review","Yesterday")],activity:[c("10:05 AM","Bulk ID cards printed (batch 14)","SIS Office","IDC-B14"),c("09:20 AM","Guardian contact updated","Student (self)","SIS-2208"),c("Yesterday","Duplicate record merged","SIS Office","SIS-DUP-31")]},"enrolment-registration":{action:"Open Registration",kpis:[r("Registered this semester","3,605","Of 3,842 enrolled","93.8%"),r("Electives allotted","2,940","Seat allocation complete","+210"),r("Pending registrations","237","Fee or hold issues","action","alert"),r("Sections formed","148","Across 42 programmes","+6")],chart:{title:"Registrations",subtitle:"Monthly, core vs elective",series:["Core","Elective"],base:520,split:.4},breakdown:{title:"Registration Holds",subtitle:"Why students are blocked",items:[["Fee due",112],["Library dues",48],["Document pending",39],["Disciplinary",6]]},actions:[d("REG-HLD","Hold review","112 students blocked for fee dues","Finance confirmation needed to release","Urgent","30 mins ago"),d("REG-ELC","Elective","Sports Psychology elective oversubscribed","84 requests for 60 seats","Pending","2 hours ago"),d("REG-SEC","Section","New section for B.P.Ed Semester 3","Faculty assignment pending","Review","Yesterday")],activity:[c("10:18 AM","Late registration window opened","Registrar","REG-WIN-3"),c("09:44 AM","Elective lottery run for 6 courses","System","REG-LOT-12"),c("Yesterday","Registration sync to LMS","System","REG-SYNC","Success")]},"academic-management":{action:"Add Course",kpis:[r("Programmes","42","UG, PG and diploma","+3"),r("Active courses","386","This semester","+18"),r("Curriculum revisions","9","Awaiting Board of Studies","pending","alert"),r("Faculty assigned","96%","Course-faculty mapping","312 faculty")],chart:{title:"Teaching Load",subtitle:"Credit hours per month, theory vs practical",series:["Theory","Practical"],base:4200,split:.45},breakdown:{title:"Courses by School",subtitle:"Running this semester",items:[["Sports Sciences",118],["Physical Education",94],["Management",72],["Computer Science & AI",64],["Humanities",38]]},actions:[d("BOS-14","Curriculum","B.Sc Sports Science syllabus revision","Board of Studies meeting on 12 Oct","Pending","1 hour ago"),d("CRS-302","Faculty load","3 courses without faculty","Strength & Conditioning lab sections","Urgent","4 hours ago"),d("CRS-288","Credit change","Sports Nutrition credits 3 → 4","Academic Council approval needed","Review","Yesterday")],activity:[c("10:02 AM","Course outcome mapping updated","Dr. R. Kaur","CRS-214"),c("09:15 AM",'New elective "Esports Management" created',"Academic Office","CRS-391"),c("Yesterday","Faculty load report exported","HoD, Sports Sciences","RPT-FL-10")]},lms:{action:"Create Course Content",kpis:[r("Active learners","3,214","Logged in this week","+6.1%"),r("Courses online","348","With published content","90%"),r("Assignments to grade","412","Across all faculty","overdue 38","alert"),r("Avg. completion","78%","Module completion rate","+3.2%")],chart:{title:"Learning Activity",subtitle:"Monthly submissions, assignments vs quizzes",series:["Assignments","Quizzes"],base:6800,split:.45},breakdown:{title:"Engagement by Programme",subtitle:"Active learners this week",items:[["B.P.Ed",820],["B.Sc Sports Science",760],["BBA Sports Mgmt",610],["B.Tech CSE",540],["M.P.Ed",484]]},actions:[d("LMS-GR","Grading","38 assignments past grading deadline","Biomechanics and Exercise Physiology","Urgent","25 mins ago"),d("LMS-PLG","Plagiarism","5 submissions flagged above 40%","Research Methods — Section B","Review","2 hours ago"),d("LMS-VID","Content","Lecture video upload failed","Sports Psychology week 6","Pending","Yesterday")],activity:[c("10:20 AM",'Quiz "Anatomy Unit 3" published',"Dr. R. Kaur","LMS-Q-884"),c("09:48 AM","142 submissions received","System","LMS-AS-219"),c("Yesterday","Discussion forum moderated","Faculty","LMS-FRM-41")]},examinations:{action:"Schedule Exam",kpis:[r("Exams scheduled","214","Mid-semester, October","+12"),r("Hall tickets issued","3,540","Of 3,605 registered","98.2%"),r("Results pending","12","Awaiting moderation","urgent","alert"),r("Pass rate","91.4%","Last semester","+1.8%")],chart:{title:"Evaluations Completed",subtitle:"Monthly, internal vs external",series:["Internal","External"],base:5200,split:.35},breakdown:{title:"Result Processing",subtitle:"Current exam cycle",items:[["Answer sheets received",7210],["Evaluated",6480],["Moderated",5120],["Published",4380]],footer:["Cycle completion","60.7%"]},actions:[d("EXM-238","Results","B.P.Ed Semester 5 results","Submitted for moderation by Controller","Urgent","1 hour ago"),d("EXM-241","Re-evaluation","27 re-evaluation requests","Fee received, evaluator assignment pending","Pending","3 hours ago"),d("EXM-244","Clash","Timetable clash for 14 students","Elective exams on same slot","Review","Yesterday")],activity:[c("10:35 AM","Results submitted for verification","Dr. Vikram Malhotra","EXM-238"),c("09:10 AM","Hall tickets generated (batch 4)","Exam Cell","HT-B4"),c("Yesterday","Question paper vault accessed","Controller of Exams","QPV-118","Warning")]},"timetable-attendance":{action:"Generate Timetable",kpis:[r("Classes today","286","Across 42 programmes","+4"),r("Avg. attendance","86.4%","This week","+1.2%"),r("Below 75%","214","Students at debarment risk","alert","alert"),r("Attendance to mark","19","Sessions not yet marked","today","muted")],chart:{title:"Attendance Sessions",subtitle:"Monthly, lectures vs practicals",series:["Lectures","Practicals"],base:5600,split:.4},breakdown:{title:"Attendance by School",subtitle:"Average this month",unit:"%",items:[["Sports Sciences",91],["Physical Education",88],["Management",85],["Computer Science & AI",83],["Humanities",80]]},actions:[d("ATT-DBR","Debarment","214 students below 75%","Warning letters to be issued","Urgent","40 mins ago"),d("TT-ROOM","Room clash","Seminar Hall B double-booked","Thursday 11:00, two sections","Pending","2 hours ago"),d("ATT-COR","Correction","6 attendance correction requests","Athletes on tournament duty","Review","Yesterday")],activity:[c("10:40 AM","Attendance marked for 64 sessions","Faculty","ATT-0610"),c("09:12 AM","Trial session roster locked","Rajinder Kumar","ATT-9041"),c("Yesterday","Timetable v3 published","Academic Office","TT-V3")]},"athlete-performance":{action:"Add Athlete",kpis:[r("Active athletes","428","16 competitive disciplines","+8.2%"),r("Fitness tests this month","312","Benchmarks recorded","+46"),r("Below benchmark","37","Need intervention plan","review","alert"),r("National-level athletes","64","Representing state or country","+5")],chart:{title:"Fitness Assessments",subtitle:"Monthly, field vs lab tests",series:["Field","Lab"],base:260,split:.35},breakdown:{title:"Athletes by Discipline",subtitle:"Top disciplines",items:[["Athletics",96],["Wrestling",58],["Hockey",52],["Shooting",41],["Boxing",38]]},actions:[d("ATH-4091","Performance","Sprint squad 100m times regressed","5 athletes slower by 0.2s or more","Urgent","1 hour ago"),d("ATH-CLR","Clearance","12 fitness clearances pending","Needed before inter-university meet","Pending","3 hours ago"),d("ATH-PLN","Plan","Off-season plan for wrestling squad","Coach submitted, HoD review","Review","Yesterday")],activity:[c("10:04 AM","Athlete performance biometric record updated","Col. Gurmeet Dhillon","ATH-4091"),c("09:30 AM","VO2 max results imported","Sports Science Lab","LAB-0610"),c("Yesterday","Wearable sync failed for 3 athletes","Wearables adapter","WRB-ERR-9","Warning")]},"training-video-analysis":{action:"Upload Video",kpis:[r("Training sessions","1,146","Logged this month","+12%"),r("Videos uploaded","524","Match and training footage","+88"),r("Reviews pending","43","Awaiting coach annotation","pending","alert"),r("Storage used","2.8 TB","Of 5 TB quota","56%","muted")],chart:{title:"Training Sessions",subtitle:"Monthly, team vs individual",series:["Team","Individual"],base:980,split:.4},breakdown:{title:"Videos by Sport",subtitle:"Uploaded this month",items:[["Hockey",132],["Athletics",118],["Wrestling",96],["Boxing",74],["Football",61]]},actions:[d("VID-773","Review","Hockey semi-final footage","Tactical review requested by head coach","Pending","2 hours ago"),d("VID-770","Annotation","Javelin technique breakdown","8 clips awaiting biomechanics notes","Review","5 hours ago"),d("VID-STR","Storage","Quota 56% used","Archive season 2025 footage","Pending","Yesterday")],activity:[c("10:22 AM",'Session plan "Speed endurance" assigned',"Coach Rajinder Kumar","TRN-552"),c("09:35 AM","24 clips tagged","Video Analyst","VID-768"),c("Yesterday","Match video shared with athlete","Coach","VID-761")]},"sports-nutrition-health":{action:"New Diet Plan",kpis:[r("Athletes on diet plans","286","Personalised nutrition","+14"),r("Physio sessions","418","This month","+9.6%"),r("Active injuries","23","Under rehabilitation","4 severe","alert"),r("Return-to-play","17","Cleared this month","+5")],chart:{title:"Clinic Visits",subtitle:"Monthly, physio vs medical",series:["Physio","Medical"],base:380,split:.38},breakdown:{title:"Injuries by Type",subtitle:"Current season",items:[["Hamstring strain",9],["Ankle sprain",7],["Shoulder",4],["Knee ligament",2],["Other",1]]},actions:[d("MED-881","Injury","ACL suspected — wrestling athlete","MRI referral needs approval","Urgent","35 mins ago"),d("NUT-214","Plan review","12 diet plans due for review","Pre-competition phase","Pending","3 hours ago"),d("MED-874","Clearance","Return-to-play for 3 athletes","Physio sign-off complete","Review","Yesterday")],activity:[c("10:28 AM","Rehab session logged","Physiotherapist","PHY-2291"),c("09:50 AM","Body composition scans uploaded","Nutritionist","NUT-BCS-14"),c("Yesterday","Supplement stock below threshold","Clinic store","NUT-STK-3","Warning")]},"tournament-events":{action:"Create Tournament",kpis:[r("Upcoming events","14","Next 60 days","+3"),r("Medals this season","86","Gold 29 · Silver 31 · Bronze 26","+12"),r("Entries pending","9","Federation registrations","deadline","alert"),r("Teams travelling","6","This month","112 athletes","muted")],chart:{title:"Medals Won",subtitle:"Monthly, individual vs team events",series:["Individual","Team"],base:14,split:.3},breakdown:{title:"Medals by Sport",subtitle:"This season",items:[["Athletics",24],["Wrestling",18],["Shooting",15],["Boxing",13],["Hockey",6]]},actions:[d("TRN-AIU","Entry","AIU Athletics entries close Friday","9 athletes not yet registered","Urgent","1 hour ago"),d("TRN-TRV","Travel","Hockey team travel to Bhopal","Rail tickets and per-diem approval","Pending","4 hours ago"),d("TRN-OFF","Officials","Technical officials for home meet","6 officials to confirm","Review","Yesterday")],activity:[c("10:15 AM","Fixture list published","Sports Office","FIX-1006"),c("09:00 AM","Results uploaded: State Boxing","Event Manager","RES-0605"),c("Yesterday","Accreditation cards printed","Sports Office","ACC-221")]},"sports-facilities":{action:"Add Facility",kpis:[r("Facilities","38","Grounds, courts, pools, gyms","+2"),r("Utilisation","81%","Booked hours this week","+6%"),r("Out of service","3","Under repair","alert","alert"),r("Safety audits due","5","This month","scheduled","muted")],chart:{title:"Facility Hours Used",subtitle:"Monthly, training vs events",series:["Training","Events"],base:3600,split:.22},breakdown:{title:"Utilisation by Facility",subtitle:"Booked hours this week",items:[["Synthetic Track",96],["Hockey Turf",88],["Aquatic Centre",74],["Wrestling Hall",70],["Indoor Stadium",63]]},actions:[d("FAC-POOL","Repair","Aquatic centre filtration pump","Vendor quote ₹2.4 L awaiting approval","Urgent","50 mins ago"),d("FAC-AUD","Safety audit","Shooting range annual audit","Due by 15 Oct","Pending","3 hours ago"),d("FAC-LGT","Upgrade","LED floodlights for hockey turf","Proposal for budget review","Review","Yesterday")],activity:[c("10:05 AM","Track marked available after resurfacing","Facility Manager","FAC-TRK"),c("09:30 AM","Gym equipment inspection logged","Facility Staff","FAC-GYM-12"),c("Yesterday","Pool chlorine level alert","Sensor","FAC-POOL-S2","Warning")]},"facility-booking":{action:"New Booking",kpis:[r("Bookings today","64","Classrooms, halls, venues","+8"),r("This month","1,412","Confirmed bookings","+11%"),r("Awaiting approval","18","Requests in queue","5 urgent","alert"),r("Cancellations","3.2%","This month","-0.8%","muted")],chart:{title:"Bookings",subtitle:"Monthly, academic vs sports venues",series:["Academic","Sports"],base:1200,split:.45},breakdown:{title:"Bookings by Venue Type",subtitle:"This month",items:[["Classrooms",520],["Sports venues",446],["Seminar halls",214],["Labs",148],["Auditorium",84]]},actions:[d("BKG-3391","Approval","Auditorium for Alumni Meet","20 Oct, 600 guests","Urgent","30 mins ago"),d("BKG-3388","Conflict","Indoor stadium double-booked","Badminton trials vs convocation rehearsal","Pending","2 hours ago"),d("BKG-3380","Recurring","Semester booking for Yoga Hall","3 days a week, Physical Education","Review","Yesterday")],activity:[c("10:10 AM","12 bookings auto-approved","System","BKG-AUTO"),c("09:25 AM","Seminar Hall A booked","HoD, Management","BKG-3392"),c("Yesterday","No-show released 4 slots","System","BKG-NS-6")]},"inventory-equipment":{action:"Issue Equipment",kpis:[r("Items in stock","12,480","Across 9 stores","+320"),r("Issued this month","1,936","Equipment and consumables","+7%"),r("Below reorder level","5","Need purchase indent","reorder","alert"),r("Overdue returns","42","Not returned on time","follow up","muted")],chart:{title:"Stock Movement",subtitle:"Monthly, issues vs returns",series:["Issued","Returned"],base:1700,split:.45},breakdown:{title:"Stock by Category",subtitle:"Items on hand",items:[["Sports equipment",4820],["Lab consumables",3110],["Stationery",2240],["Medical supplies",1310],["IT accessories",1e3]]},actions:[d("INV-RO","Reorder","Hockey balls below reorder level","40 left, reorder level 120","Urgent","1 hour ago"),d("INV-OVD","Overdue","42 items overdue for return","Mostly athletics spikes and kits","Pending","3 hours ago"),d("INV-AUD","Stock audit","Annual stock verification","Central store, 14 Oct","Review","Yesterday")],activity:[c("10:00 AM","24 javelins issued to athletics squad","Store Keeper","ISS-6610"),c("09:20 AM","GRN recorded for lab consumables","Store Keeper","GRN-2281"),c("Yesterday","Low stock alert: first-aid kits","System","INV-LS-11","Warning")]},"asset-management":{action:"Register Asset",kpis:[r("Fixed assets","6,214","Tagged and registered","+86"),r("Asset value","₹184 Cr","Net book value","+2.1%"),r("Audit due","312","Physical verification pending","due","alert"),r("Disposals pending","27","Condemnation committee","review","muted")],chart:{title:"Assets Added",subtitle:"Monthly, equipment vs infrastructure",series:["Equipment","Infrastructure"],base:70,split:.25},breakdown:{title:"Value by Category",subtitle:"₹ crore, net book value",items:[["Buildings",112],["Sports infrastructure",38],["Lab equipment",17],["IT hardware",11],["Vehicles",6]]},actions:[d("AST-AUD","Verification","312 assets due for verification","Block C and Sports Complex","Urgent","2 hours ago"),d("AST-DSP","Disposal","27 assets for condemnation","Committee meeting on 18 Oct","Pending","5 hours ago"),d("AST-TRF","Transfer","Treadmills moved to new gym","Location update approval","Review","Yesterday")],activity:[c("10:25 AM","86 assets tagged with QR labels","Asset Officer","AST-TAG-9"),c("09:15 AM","Depreciation run for September","System","AST-DEP-09"),c("Yesterday","Missing asset reported","Facility Staff","AST-MIS-4","Warning")]},maintenance:{action:"Raise Work Order",kpis:[r("Open work orders","58","Across campus","-6"),r("Completed this month","214","Closed work orders","+12%"),r("Overdue","11","Past target date","escalate","alert"),r("Preventive tasks","92%","On schedule","+4%")],chart:{title:"Work Orders Closed",subtitle:"Monthly, corrective vs preventive",series:["Corrective","Preventive"],base:190,split:.4},breakdown:{title:"Open Orders by Trade",subtitle:"Current backlog",items:[["Electrical",19],["Plumbing",14],["Civil",11],["HVAC",8],["Carpentry",6]]},actions:[d("WO-7781","Electrical","Hostel B power fluctuation","Reported by 40 residents","Urgent","20 mins ago"),d("WO-7774","Plumbing","Aquatic centre shower leakage","Vendor visit scheduled","Pending","3 hours ago"),d("WO-7769","AMC","Lift AMC renewal","Quote from 2 vendors received","Review","Yesterday")],activity:[c("10:30 AM","Work order WO-7779 closed","Maintenance Team","WO-7779"),c("09:40 AM","Preventive check: DG sets","Electrical","PM-DG-10"),c("Yesterday","SLA breached on WO-7760","System","WO-7760","Warning")]},"fees-accounts":{action:"Generate Invoice",kpis:[r("Collected this term","₹8.42 Cr","Autumn 2026","+12.4%"),r("Collection rate","91%","Of billed fees","+3%"),r("Outstanding dues","₹74 L","312 students","follow up","alert"),r("Reconciled","₹1.28 Cr","SBIePay, this week","matched")],chart:{title:"Fee Collection",subtitle:"₹ lakh per month, online vs counter",series:["Online","Counter"],base:140,split:.15},breakdown:{title:"Collection by Fee Head",subtitle:"₹ lakh, this term",items:[["Tuition",512],["Hostel",168],["Examination",74],["Sports & activity",52],["Transport",36]]},actions:[d("PAY-20481","Payment","Vendor payment for athletic track","Awaiting financial concurrence","Pending","24 mins ago"),d("FEE-REF","Refund","14 refund requests","Withdrawn admissions","Review","3 hours ago"),d("FEE-REC","Reconciliation","₹3.2 L unmatched in SBIePay","Transaction IDs missing","Urgent","Yesterday")],activity:[c("10:42 AM","Payment request created","P. Singh, CA","PAY-20481"),c("09:30 AM","Daily SBIePay settlement imported","System","SET-0610"),c("Yesterday","Fee reminder SMS sent to 312 students","Notification service","NTF-FEE-6")]},"budget-grants":{action:"New Budget Head",kpis:[r("Annual budget","₹96 Cr","FY 2026–27","+8%"),r("Utilised","48%","₹46 Cr spent","on track"),r("Grant UCs due","4","Utilisation certificates","deadline","alert"),r("Active grants","19","Khelo India, UGC, state","+3")],chart:{title:"Expenditure",subtitle:"₹ lakh per month, revenue vs capital",series:["Revenue","Capital"],base:720,split:.35},breakdown:{title:"Spend by Head",subtitle:"₹ crore, year to date",items:[["Salaries",21],["Sports infrastructure",11],["Academic",6],["Hostels",5],["Administration",3]]},actions:[d("UC-KI-26","Utilisation","Khelo India grant UC due","Submit by 31 Oct","Urgent","1 hour ago"),d("BUD-RE","Re-appropriation","₹40 L from Admin to Sports","Finance Committee approval","Pending","4 hours ago"),d("GRT-UGC","Grant","UGC research grant installment","Release letter received","Review","Yesterday")],activity:[c("10:12 AM","Quarterly budget report generated","Finance Officer","RPT-BUD-Q2"),c("09:20 AM","Grant ledger updated","Accounts","GRT-LED-19"),c("Yesterday","Head overspend warning: Travel","System","BUD-WRN-4","Warning")]},procurement:{action:"Raise Indent",kpis:[r("Open indents","46","Department requests","+9"),r("POs issued","₹3.6 Cr","This quarter","+14%"),r("Tenders live","5","On GeM and e-tender","closing","alert"),r("Vendors","284","Empanelled","+12")],chart:{title:"Purchase Orders",subtitle:"Monthly count, GeM vs open tender",series:["GeM","Open tender"],base:60,split:.3},breakdown:{title:"Spend by Category",subtitle:"₹ lakh, this quarter",items:[["Sports equipment",148],["Lab equipment",92],["IT",64],["Furniture",38],["Services",18]]},actions:[d("TND-112","Tender","Synthetic track resurfacing","Technical evaluation due","Urgent","2 hours ago"),d("IND-889","Indent","Boxing rings ×2","Budget availability check","Pending","4 hours ago"),d("PO-4410","PO","Gym equipment PO","Ready for Registrar signature","Review","Yesterday")],activity:[c("10:08 AM","PO issued on GeM","Purchase Officer","PO-4412"),c("09:45 AM","Bid opened for tender TND-110","Purchase Committee","TND-110"),c("Yesterday","GeM API key regenerated","Dr. A. Sharma","SEC-KEY-819")]},"hr-payroll":{action:"Run Payroll",kpis:[r("Employees","612","Teaching and non-teaching","+8"),r("Payroll (Sept)","₹4.1 Cr","Processed on time","paid"),r("Leave requests","23","Awaiting approval","pending","alert"),r("Vacancies","34","Sanctioned posts open","recruiting","muted")],chart:{title:"Payroll Cost",subtitle:"₹ lakh per month, teaching vs non-teaching",series:["Teaching","Non-teaching"],base:405,split:.38},breakdown:{title:"Staff by Category",subtitle:"Current headcount",items:[["Faculty",312],["Coaches",42],["Administrative",138],["Technical",72],["Support",48]]},actions:[d("LV-2291","Leave","23 leave requests pending","7 earned leave, 16 casual","Pending","30 mins ago"),d("PAY-OCT","Payroll","October payroll draft","DA arrears to include","Review","3 hours ago"),d("REC-COACH","Recruitment","Interview panel for 4 coaches","Dates to confirm","Urgent","Yesterday")],activity:[c("10:20 AM","Joining recorded: Assistant Professor","HR Office","EMP-612"),c("09:05 AM","Salary slips emailed","System","PAY-SEP"),c("Yesterday","Biometric attendance sync delayed","System","HR-BIO-2","Warning")]},"e-office":{action:"Create File",kpis:[r("Files in movement","418","Across 26 sections","+31"),r("Closed this month","296","Decisions recorded","+9%"),r("Pending > 7 days","38","Delayed files","escalate","alert"),r("Avg. turnaround","3.4 days","Per file","-0.6 d")],chart:{title:"Files Processed",subtitle:"Monthly, created vs closed",series:["Created","Closed"],base:320,split:.47},breakdown:{title:"Pending by Section",subtitle:"Files awaiting action",items:[["Registrar",84],["Finance",72],["Academic",58],["Sports",46],["Estate",31]]},actions:[d("EF-5521","File","Convocation 2026 arrangements","With Registrar for 9 days","Urgent","1 hour ago"),d("EF-5514","Noting","MoU with State Sports Dept.","Legal opinion attached","Pending","4 hours ago"),d("EF-5509","Circular","Revised travel allowance rules","Draft for VC approval","Review","Yesterday")],activity:[c("10:15 AM","File EF-5518 forwarded to Finance","Section Officer","EF-5518"),c("09:30 AM","Digital signature applied","Registrar","EF-5502"),c("Yesterday","12 dak entries digitised","Dak Section","DAK-0605")]},hostel:{action:"Allot Room",kpis:[r("Residents","1,846","In 8 hostels","+42"),r("Occupancy","94%","Of 1,960 beds","+3%"),r("Complaints open","27","Maintenance and mess","urgent 6","alert"),r("Mess satisfaction","4.1 / 5","Monthly survey","+0.2")],chart:{title:"Hostel Complaints",subtitle:"Monthly, maintenance vs mess",series:["Maintenance","Mess"],base:70,split:.35},breakdown:{title:"Occupancy by Hostel",subtitle:"Residents",items:[["Milkha Singh Boys",420],["Mary Kom Girls",360],["Dhyan Chand Boys",340],["P.T. Usha Girls",310],["International",96]]},actions:[d("HST-B","Electrical","Hostel B power fluctuation","Work order WO-7781 raised","Urgent","20 mins ago"),d("HST-ALT","Allotment","18 room change requests","Mostly athletes moving to sports block","Pending","3 hours ago"),d("HST-MESS","Mess","Athlete diet menu revision","Nutritionist recommendations","Review","Yesterday")],activity:[c("10:00 AM","Visitor entries logged: 46","Hostel Warden","VIS-0610"),c("09:10 AM","Room 214 allotted","Hostel Office","HST-ALT-88"),c("Yesterday","Late entry recorded","Gate system","HST-GATE-12","Warning")]},transport:{action:"Add Route",kpis:[r("Bus passes","1,124","Students and staff","+38"),r("Routes","22","28 vehicles","+1"),r("Vehicles in service","25","3 under maintenance","check","alert"),r("On-time trips","93%","This month","+2%")],chart:{title:"Trips Operated",subtitle:"Monthly, campus routes vs event travel",series:["Routes","Events"],base:1300,split:.12},breakdown:{title:"Riders by Route",subtitle:"Daily average",items:[["Route 1",386],["Route 2",214],["Route 3",168],["Route 4",142],["Route 5",98]]},actions:[d("TRP-HKY","Event travel","Bus for hockey team to Ludhiana","Departure Saturday 6 AM","Urgent","1 hour ago"),d("VEH-12","Fitness","Vehicle fitness certificate due","PB-11-CK-4412","Pending","5 hours ago"),d("RTE-NEW","Route","New route request: Bahadurgarh","46 students interested","Review","Yesterday")],activity:[c("10:05 AM","GPS alert cleared on Route 7","Transport Office","GPS-7"),c("09:00 AM","38 passes issued","Transport Office","PASS-0610"),c("Yesterday","Route 3 delayed 25 mins","GPS","RTE-3-DLY","Warning")]},library:{action:"Issue Book",kpis:[r("Collection","48,210","Books, journals, e-resources","+620"),r("Loans active","2,364","Currently issued","+5%"),r("Overdue","186","Past due date","fines","alert"),r("E-resource sessions","9,840","This month","+18%")],chart:{title:"Circulation",subtitle:"Monthly, print vs digital",series:["Print","Digital"],base:2900,split:.5},breakdown:{title:"Loans by Subject",subtitle:"Active loans",items:[["Sports Science",742],["Physical Education",610],["Management",412],["Computer Science",356],["Humanities",244]]},actions:[d("LIB-OVD","Overdue","186 overdue loans","Send reminder and fine notices","Pending","40 mins ago"),d("LIB-ACQ","Acquisition","124 titles requested by faculty","Budget ₹4.6 L","Review","4 hours ago"),d("LIB-SUB","Subscription","SPORTDiscus renewal","Expires 31 Oct","Urgent","Yesterday")],activity:[c("10:18 AM","62 books returned","Circulation Desk","LIB-RET-0610"),c("09:35 AM","New arrivals catalogued","Librarian","LIB-CAT-44"),c("Yesterday","RFID gate alarm","Security gate","LIB-GATE-3","Warning")]},"placement-career":{action:"Add Drive",kpis:[r("Students placed","312","Batch 2026, so far","+18%"),r("Recruiters","64","Visited campus","+11"),r("Offers awaiting response","27","Expire this week","follow up","alert"),r("Median package","₹5.8 LPA","Batch 2026","+0.6")],chart:{title:"Offers Made",subtitle:"Monthly, on-campus vs off-campus",series:["On-campus","Off-campus"],base:48,split:.3},breakdown:{title:"Placements by Sector",subtitle:"Batch 2026",items:[["Sports management",98],["Fitness & wellness",76],["Education",64],["IT & analytics",52],["Government",22]]},actions:[d("PLC-DEC","Drive","Decathlon recruitment drive","Confirm venue and shortlist","Urgent","1 hour ago"),d("PLC-OFR","Offers","27 offers pending acceptance","Deadline Friday","Pending","3 hours ago"),d("PLC-INT","Internship","SAI internship nominations","15 seats, 48 applicants","Review","Yesterday")],activity:[c("10:22 AM","8 offers released","Placement Cell","PLC-OFR-41"),c("09:15 AM","Resume workshop scheduled","Career Services","PLC-WS-6"),c("Yesterday","Recruiter registered","Recruiter portal","PLC-REC-64")]},alumni:{action:"Create Event",kpis:[r("Alumni registered","8,640","In the directory","+214"),r("Donations (FY)","₹62 L","Scholarships and facilities","+22%"),r("Profiles to verify","96","New registrations","pending","alert"),r("Event RSVPs","412","Alumni Meet 2026","+120")],chart:{title:"Alumni Engagement",subtitle:"Monthly, event attendance vs mentoring",series:["Events","Mentoring"],base:260,split:.4},breakdown:{title:"Alumni by Sector",subtitle:"Where they work",items:[["Coaching",2140],["Teaching",1980],["Armed forces & police",1420],["Sports admin",1180],["Corporate",920]]},actions:[d("ALM-MEET","Event","Alumni Meet 2026 logistics","Auditorium booking BKG-3391","Urgent","30 mins ago"),d("ALM-VER","Verification","96 profiles to verify","Match with degree records","Pending","4 hours ago"),d("ALM-DON","Donation","₹5 L scholarship pledge","Receipt and 80G certificate","Review","Yesterday")],activity:[c("10:10 AM","Newsletter sent to 8,640 alumni","Alumni Office","ALM-NL-10"),c("09:25 AM","Donation received ₹50,000","Payment gateway","DON-2291"),c("Yesterday","Mentor matched with 12 students","Alumni Office","ALM-MNT-12")]},grievance:{action:"Register Grievance",kpis:[r("Open cases","14","SGRC, anti-ragging, POSH-ICC","-3"),r("Resolved this year","128","Within timeline","94%"),r("Escalated","2","To Proctorial Committee","urgent","alert"),r("Avg. resolution","9 days","Target 15 days","-2 d")],chart:{title:"Grievances Received",subtitle:"Monthly, academic vs non-academic",series:["Academic","Non-academic"],base:14,split:.45},breakdown:{title:"Open Cases by Committee",subtitle:"Current",items:[["SGRC",6],["Hostel",4],["Anti-ragging",2],["POSH-ICC",1],["Examination",1]]},actions:[d("GRV-301","Escalation","Hostel grievance escalated","Proctorial Committee hearing","Urgent","1 hour ago"),d("GRV-298","Hearing","SGRC hearing on evaluation","Schedule within 7 days","Pending","4 hours ago"),d("GRV-294","Closure","Anti-ragging case closure report","Committee sign-off","Review","Yesterday")],activity:[c("10:00 AM","Case GRV-296 resolved","SGRC","GRV-296"),c("09:20 AM","Anti-ragging affidavit drive","Dean Students","ARG-2026"),c("Yesterday","Case nearing deadline","System","GRV-292","Warning")]},rti:{action:"Log RTI Request",kpis:[r("Requests this year","64","Under RTI Act 2005","+9"),r("Disposed in time","96%","Within 30 days","+2%"),r("Nearing deadline","3","Due within 48 hours","urgent","alert"),r("First appeals","4","Pending with FAA","review","muted")],chart:{title:"RTI Requests",subtitle:"Monthly, received vs disposed",series:["Received","Disposed"],base:6,split:.48},breakdown:{title:"Requests by Topic",subtitle:"This year",items:[["Admissions",21],["Recruitment",14],["Finance",12],["Examinations",10],["Sports",7]]},actions:[d("RTI-2611","Deadline","Recruitment records request","Due in 36 hours","Urgent","10 mins ago"),d("RTI-2608","Transfer","Request on state sports policy","Transfer to Sports Department","Pending","3 hours ago"),d("APL-04","First appeal","Appeal on admission merit list","Hearing with FAA","Review","Yesterday")],activity:[c("10:05 AM","Reply dispatched for RTI-2604","PIO","RTI-2604"),c("09:40 AM","Information sought from Exam Cell","APIO","RTI-2609"),c("Yesterday","Quarterly RTI return filed","PIO","RTI-QR-2")]},"iqac-accreditation":{action:"Upload Evidence",kpis:[r("NAAC criteria","7","Self-study report","82% ready"),r("Evidence files","1,412","Uploaded to repository","+96"),r("Action items open","18","From IQAC meetings","due","alert"),r("Feedback collected","3,120","Students and stakeholders","+640")],chart:{title:"Evidence Uploaded",subtitle:"Monthly, documents vs data templates",series:["Documents","Templates"],base:180,split:.4},breakdown:{title:"SSR Readiness by Criterion",subtitle:"Share complete",unit:"%",items:[["Curricular aspects",92],["Teaching-learning",88],["Research",71],["Infrastructure",90],["Student support",84]]},actions:[d("IQAC-AI-18","Action item","Research publication data missing","Criterion 3, 4 departments","Urgent","2 hours ago"),d("IQAC-AQAR","AQAR","AQAR 2025–26 draft","Review by IQAC coordinator","Pending","5 hours ago"),d("IQAC-FB","Feedback","Employer feedback survey","Launch to 64 recruiters","Review","Yesterday")],activity:[c("10:30 AM","96 evidence files uploaded","Departments","IQAC-EV-96"),c("09:10 AM","IQAC meeting minutes published","IQAC Coordinator","IQAC-MOM-9"),c("Yesterday","Data template rejected","IQAC","IQAC-TPL-12","Warning")]},"regulatory-reports":{action:"Prepare Report",kpis:[r("Returns filed","22","UGC, AISHE, NIRF this year","+4"),r("On-time filing","95%","Statutory deadlines","+5%"),r("Due this month","3","AISHE, NIRF, state return","deadline","alert"),r("Data completeness","88%","Fields auto-filled from modules","+9%")],chart:{title:"Reports Filed",subtitle:"Monthly, central vs state",series:["Central","State"],base:4,split:.4},breakdown:{title:"Reports by Regulator",subtitle:"This year",items:[["UGC",8],["AISHE",4],["NIRF",3],["State Govt.",5],["NAAC",2]]},actions:[d("AISHE-26","Return","AISHE 2025–26 data upload","Due 20 Oct","Urgent","1 hour ago"),d("NIRF-27","Ranking","NIRF data capture","Faculty and research sections","Pending","4 hours ago"),d("UGC-SFS","Compliance","UGC self-financing course return","Registrar sign-off","Review","Yesterday")],activity:[c("10:10 AM","Student data exported for AISHE","MIS Cell","RPT-AISHE"),c("09:30 AM","Compliance calendar updated","Registrar Office","CAL-COMP"),c("Yesterday","Validation errors in NIRF draft","System","NIRF-VAL","Warning")]},helpdesk:{action:"New Ticket",kpis:[r("Open tickets","24","Hostel, Wi-Fi & LMS","-5"),r("Resolved this week","186","Closed tickets","+12%"),r("High priority","6","Need attention now","urgent","alert"),r("Avg. resolution","4.2 h","This week","-0.8 h")],chart:{title:"Tickets",subtitle:"Monthly, raised vs resolved",series:["Raised","Resolved"],base:820,split:.48},breakdown:{title:"Open Tickets by Category",subtitle:"Current queue",items:[["Wi-Fi & network",9],["Hostel",6],["LMS access",4],["Fee portal",3],["Email",2]]},actions:[d("TCK-8830","Network","Wi-Fi down in Sports Complex","Affecting 3 halls","Urgent","15 mins ago"),d("TCK-8826","LMS","Students cannot submit quiz","Exercise Physiology, Section A","Pending","1 hour ago"),d("TCK-8819","Access","Email account for new faculty","8 accounts to create","Review","Yesterday")],activity:[c("09:48 AM","Ticket closed: Campus Wi-Fi credentials reissued","Sunita Verma","TCK-8812"),c("09:20 AM","14 tickets auto-assigned","System","TCK-AUTO"),c("Yesterday","Ticket reopened by user","Student","TCK-8794","Warning")]},"sla-management":{action:"Define SLA",kpis:[r("SLA policies","18","By ticket category","+2"),r("Met this month","94%","Within target time","+3%"),r("Breaches","11","This month","review","alert"),r("At risk now","4","Close to breach","watch","muted")],chart:{title:"SLA Outcomes",subtitle:"Monthly, met vs breached",series:["Met","Breached"],base:780,split:.06},breakdown:{title:"Breaches by Team",subtitle:"This month",items:[["Network",4],["Maintenance",3],["Hostel",2],["Finance",1],["Academic",1]]},actions:[d("SLA-NET","Breach","Network team: 4 breaches","Root-cause review","Urgent","1 hour ago"),d("SLA-ESC","Escalation","Escalation matrix update","Add hostel wardens","Pending","4 hours ago"),d("SLA-NEW","Policy","SLA for sports equipment requests","Proposed 48-hour target","Review","Yesterday")],activity:[c("10:00 AM","SLA timer paused (awaiting user)","System","TCK-8826"),c("09:15 AM","Monthly SLA report generated","Support Lead","RPT-SLA-09"),c("Yesterday","SLA breached on WO-7760","System","WO-7760","Warning")]},"knowledge-base":{action:"Write Article",kpis:[r("Articles","214","Published","+9"),r("Views this month","12,480","Self-service reads","+21%"),r("Outdated articles","17","Need review","update","alert"),r("Ticket deflection","31%","Solved without a ticket","+4%")],chart:{title:"Article Views",subtitle:"Monthly, students vs staff",series:["Students","Staff"],base:10500,split:.3},breakdown:{title:"Top Articles",subtitle:"Views this month",items:[["Connect to campus Wi-Fi",2410],["Pay fees online",1980],["Reset LMS password",1640],["Book a sports facility",1120],["Apply for hostel",880]]},actions:[d("KB-REV","Review","17 articles need review","Older than 12 months","Pending","2 hours ago"),d("KB-NEW","Gap","No article for exam re-evaluation","22 tickets on this topic","Urgent","5 hours ago"),d("KB-TRN","Translation","Regional-language versions of top 10","Translator assigned","Review","Yesterday")],activity:[c("10:12 AM","Article updated: Fee portal guide","Support Staff","KB-114"),c("09:30 AM","Article published: Facility booking","Support Lead","KB-214"),c("Yesterday","Low rating on Wi-Fi article","Users","KB-021","Warning")]},"incident-management":{action:"Report Incident",kpis:[r("Open incidents","5","Under investigation","-2"),r("Resolved this month","23","Closed with RCA","+4"),r("Major incidents","1","Service-wide impact","active","alert"),r("Mean time to restore","1.8 h","This month","-0.5 h")],chart:{title:"Incidents",subtitle:"Monthly, minor vs major",series:["Minor","Major"],base:24,split:.12},breakdown:{title:"Incidents by Service",subtitle:"This quarter",items:[["Network",21],["Power",12],["LMS",8],["Fee portal",5],["Email",3]]},actions:[d("INC-114","Major","Sports Complex network outage","Fibre cut, vendor on site","Urgent","15 mins ago"),d("PRB-022","Problem","Recurring LMS slowness","RCA due this week","Pending","4 hours ago"),d("INC-110","Post-mortem","Fee portal downtime review","Report ready for sign-off","Review","Yesterday")],activity:[c("10:05 AM","Incident INC-114 declared major","Support Lead","INC-114"),c("09:20 AM","Problem record PRB-022 linked","Support Staff","PRB-022"),c("Yesterday","Unauthorized download attempt blocked","RBAC policy","HR-PAYROLL-CONFIDENTIAL","Failed")]},"amc-vendor-support":{action:"Add Contract",kpis:[r("Active AMCs","46","Equipment and services","+3"),r("Annual value","₹2.9 Cr","AMC spend","+6%"),r("Expiring in 30 days","5","Renewal needed","renew","alert"),r("Vendor SLA met","91%","Service visits on time","+2%")],chart:{title:"Service Visits",subtitle:"Monthly, scheduled vs breakdown calls",series:["Scheduled","Breakdown"],base:120,split:.3},breakdown:{title:"AMC Value by Category",subtitle:"₹ lakh per year",items:[["Sports equipment",96],["IT & network",82],["Lifts & HVAC",54],["Lab equipment",38],["Security systems",20]]},actions:[d("AMC-LIFT","Renewal","Lift AMC expires 30 Oct","Quotes from 2 vendors received","Urgent","1 hour ago"),d("AMC-GYM","Service","Gym equipment quarterly service","Vendor visit to confirm","Pending","5 hours ago"),d("AMC-PEN","Penalty","Penalty for missed visits","Network vendor, 3 visits","Review","Yesterday")],activity:[c("10:20 AM","Service report uploaded","Vendor portal","AMC-SR-221"),c("09:10 AM","Contract renewed: CCTV AMC","Purchase Officer","AMC-CCTV"),c("Yesterday","Vendor missed scheduled visit","System","AMC-MISS-3","Warning")]},portfolio:{action:"New Portfolio",kpis:[r("Active portfolios","1,126","Learners with a live portfolio","+14%"),r("Items added (30 days)","3,480","Artworks, showreels, designs, papers","+9.2%"),r("Awaiting review","64","Submitted to mentors","18 overdue","alert"),r("Published","812","Shared on public profile","72%","muted")],chart:{title:"Portfolio Items Added",subtitle:"Monthly, creative works vs research & teaching",series:["Creative works","Research & teaching"],base:290,split:.35},breakdown:{title:"Portfolio Types",subtitle:"Items by type",items:[["Artworks & designs",1240],["Showreels & media",860],["Repertoire",540],["Teaching portfolios",420],["Research portfolios",380]]},actions:[d("PRT-412","Review","Final-year design portfolio","Mentor review due before jury","Urgent","30 mins ago"),d("PRT-409","Showreel","Film showreel upload too large","Re-encode and resubmit requested","Pending","3 hours ago"),d("PRT-401","Publish","12 portfolios ready to publish","Consent forms received","Review","Yesterday")],activity:[c("10:20 AM","Showreel added to performing arts portfolio","Student","PRT-415"),c("09:05 AM","Mentor feedback posted on design portfolio","Faculty","PRT-412"),c("Yesterday","Portfolio published to public profile","Student","PRT-398")]},projects:{action:"New Project",kpis:[r("Active projects","214","Capstone, film, research, live business","+18"),r("Teams","186","Average 3.4 members","+11"),r("Milestones due (7 days)","42","Across all projects","9 at risk","alert"),r("Completed this term","58","Final review passed","+22%")],chart:{title:"Milestones Completed",subtitle:"Monthly, on time vs late",series:["On time","Late"],base:120,split:.18},breakdown:{title:"Projects by Type",subtitle:"Active this term",items:[["Capstone",72],["Research",54],["Live business",38],["Film",29],["Artwork",21]]},actions:[d("PRJ-221","Milestone","Capstone mid-term review","9 teams missing prototype demo","Urgent","1 hour ago"),d("PRJ-217","Team change","Member transfer request","Student asked to move between teams","Pending","4 hours ago"),d("PRJ-210","Final review","Live business pitch panel","Panel of 3 to be confirmed","Review","Yesterday")],activity:[c("10:05 AM",'Milestone "Prototype" marked complete',"Team Lead","PRJ-219"),c("09:30 AM","Supervisor feedback added","Faculty","PRJ-221"),c("Yesterday","New film project created","Student","PRJ-224")]},"selection-process":{action:"Schedule Round",kpis:[r("Open selections","12","Auditions, squads, jury, moot court","+3"),r("Applicants","846","Across open selections","+21%"),r("Rounds this week","9","Auditions and jury rounds","3 today","muted"),r("Selected","132","Final lists published","15.6%")],chart:{title:"Applicants per Month",subtitle:"Shortlisted vs not shortlisted",series:["Shortlisted","Not shortlisted"],base:140,split:.55},breakdown:{title:"Selection Funnel",subtitle:"Current cycle",items:[["Applications",846],["Shortlisted",384],["Auditions / jury rounds",241],["Team selection",168],["Supervisor allocation",132]],footer:["Selection rate","15.6%"]},actions:[d("SEL-118","Jury round","Theatre casting panel","Two jurors not yet confirmed","Urgent","45 mins ago"),d("SEL-115","Squad","Inter-university football squad","Coach shortlist awaits approval","Pending","2 hours ago"),d("SEL-111","Allocation","Research supervisor allocation","18 students without supervisor","Review","Yesterday")],activity:[c("10:15 AM","Audition slots published","Coordinator","SEL-120"),c("09:10 AM","Moot court team list finalised","Faculty","SEL-117"),c("Yesterday","Shortlist exported for jury","Coordinator","SEL-116")]},productions:{action:"New Production",kpis:[r("Upcoming events","18","Next 30 days","+5"),r("Registrations","2,340","Participants and audience","+26%"),r("Venues booked","11","Halls, studios, auditoria","2 pending","alert"),r("Completed this term","34","Performances, exhibitions, hackathons","+8")],chart:{title:"Event Attendance",subtitle:"Monthly, participants vs audience",series:["Participants","Audience"],base:900,split:.6},breakdown:{title:"Events by Type",subtitle:"This academic year",items:[["Performances",22],["Exhibitions",16],["Competitions",14],["Hackathons",9],["Screenings",8],["Conferences",6]]},actions:[d("PRD-061","Venue","Annual showcase main hall","Booking clash with convocation rehearsal","Urgent","1 hour ago"),d("PRD-058","Budget","Hackathon prize budget","Finance approval pending","Pending","5 hours ago"),d("PRD-055","Programme","Film screening schedule","Final running order to review","Review","Yesterday")],activity:[c("10:30 AM","Exhibition registrations opened","Coordinator","PRD-063"),c("09:20 AM","Recital programme published","Faculty","PRD-060"),c("Yesterday","Conference speakers confirmed","Coordinator","PRD-057")]},"field-training":{action:"New Placement",kpis:[r("Learners on placement","486","Clinical, teaching, farm, internships, court","+12%"),r("Host sites","74","Hospitals, schools, farms, firms, courts","+6"),r("Logbooks to verify","58","Supervisor sign-off pending","14 overdue","alert"),r("Completed hours","38,200","This term","+9.8%")],chart:{title:"Placement Hours Logged",subtitle:"Monthly, verified vs pending",series:["Verified","Pending"],base:6200,split:.22},breakdown:{title:"Placements by Type",subtitle:"Current term",items:[["Internships",162],["Clinical rotations",118],["Teaching practice",96],["Farm rotations",64],["Court visits",46]]},actions:[d("FLD-204","Logbook","Clinical rotation logbooks","14 entries past the 7-day window","Urgent","40 mins ago"),d("FLD-199","Host site","New internship partner","MoU awaiting signature","Pending","3 hours ago"),d("FLD-196","Evaluation","Teaching practice assessments","Mentor scores to review","Review","Yesterday")],activity:[c("10:00 AM","Placement assigned to host school","Coordinator","FLD-207"),c("08:50 AM","Logbook verified by supervisor","Faculty","FLD-203"),c("Yesterday","Farm rotation schedule published","Coordinator","FLD-201")]},"skill-progress":{action:"New Assessment",kpis:[r("Learners tracked","2,140","With at least one assessment","+16%"),r("Assessments (30 days)","5,860","Technique, fitness, practicum, competencies","+11%"),r("Improving","68%","Score up since last term","+4 pts"),r("Needs attention","146","Declining two assessments in a row","review","alert")],chart:{title:"Assessments Recorded",subtitle:"Monthly, improving vs needs attention",series:["Improving","Needs attention"],base:820,split:.2},breakdown:{title:"Assessments by Area",subtitle:"Last 30 days",items:[["Technique",1980],["Competencies",1460],["Fitness",1320],["Practicum",1100]]},actions:[d("SKL-330","Rubric","Competency rubric update","New level descriptors need approval","Pending","2 hours ago"),d("SKL-326","Follow-up","146 learners declining","Assign mentors for follow-up","Urgent","3 hours ago"),d("SKL-321","Review","End-of-term progress reports","Ready for faculty review","Review","Yesterday")],activity:[c("10:25 AM","Fitness test results imported","Coach","SKL-333"),c("09:15 AM","Practicum assessment recorded","Faculty","SKL-331"),c("Yesterday","Skill framework published","Coordinator","SKL-328")]},identity:{action:"Add User",kpis:[r("User accounts","4,826","Across all roles","+3.1%"),r("Roles in use","16","From the academy profile","muted","muted"),r("Sign-ins (7 days)","18,420","Email and password","+6.4%"),r("Failed sign-ins","212","Last 7 days","review","alert")],chart:{title:"Sign-ins",subtitle:"Monthly, successful vs failed",series:["Successful","Failed"],base:72e3,split:.03},breakdown:{title:"Users by Role",subtitle:"Top roles",items:[["Student",3414],["Athlete",428],["Faculty / Instructor",312],["Coach",42],["Finance Staff",8]]},actions:[d("IDN-090","Accounts","28 accounts never signed in","Invited more than 14 days ago","Review","2 hours ago"),d("IDN-087","Failed sign-ins","Repeated failures on one account","Check with the user","Urgent","3 hours ago"),d("IDN-084","Role change","HoD role requested for faculty","Organisation admin to confirm","Pending","Yesterday")],activity:[c("10:40 AM","User account created","Organisation Admin","IDN-093"),c("09:55 AM","Role assigned: Coach","Organisation Admin","IDN-092"),c("Yesterday","Account signed in for the first time","User","IDN-089")]},tenancy:{action:"View Organisation",kpis:[r("Organisations","38","Registered on the platform","+4"),r("Pending approval","3","Academic packages awaiting super admin","review","alert"),r("Active","31","Can sign in","81.6%"),r("Academy types in use","9","Of 15 profiles","muted","muted")],chart:{title:"Registrations",subtitle:"Monthly, approved vs pending",series:["Approved","Pending"],base:6,split:.25},breakdown:{title:"Organisations by Academy Type",subtitle:"All organisations",items:[["Sports College",11],["Engineering College",8],["Arts Academy",6],["Law College",5],["Medical College",4]]},actions:[d("TEN-031","Approval","Academic package awaiting approval","Registered and email verified","Urgent","1 hour ago"),d("TEN-028","Package change","Change of academy type requested","Super admin to approve","Pending","6 hours ago"),d("TEN-025","Override","Module outside plan requested","Review entitlement override","Review","Yesterday")],activity:[c("10:12 AM","tenancy.organisation.registered","System","TEN-033"),c("09:40 AM","tenancy.organisation.approved","Super Admin","TEN-030"),c("Yesterday","tenancy.entitlement.changed","Organisation Admin","TEN-027")]},billing:{action:"View Plans",kpis:[r("Subscriptions","38","One per organisation","+4"),r("On trial","9","Trial plan","3 ending soon","alert"),r("Paid plans","29","Standard and premium","76.3%"),r("Upgrades (30 days)","5","Trial to paid","+2")],chart:{title:"Subscriptions",subtitle:"Monthly, paid vs trial",series:["Paid","Trial"],base:30,split:.25},breakdown:{title:"Organisations by Plan",subtitle:"Current subscriptions",items:[["Standard",18],["Premium",11],["Trial",9]]},actions:[d("BIL-044","Trial","3 trials end this week","Reminders sent to organisation admins","Urgent","2 hours ago"),d("BIL-041","Upgrade","Upgrade to premium requested","Payment adapter not configured","Pending","5 hours ago"),d("BIL-038","Plan","Standard plan limits update","Review student limit","Review","Yesterday")],activity:[c("10:05 AM","billing.subscription.started","System","BIL-046"),c("09:22 AM","billing.subscription.upgraded","Organisation Admin","BIL-043"),c("Yesterday","billing.trial.expired","System","BIL-040","Warning")]},workflow:{action:"New Workflow",kpis:[r("Active workflows","24","Approval and state machines","+3"),r("Items in flight","186","Awaiting a step","+12"),r("Overdue steps","17","Past their SLA","escalate","alert"),r("Completed (30 days)","1,420","Approvals closed","+8.6%")],chart:{title:"Approvals Completed",subtitle:"Monthly, within SLA vs late",series:["Within SLA","Late"],base:1300,split:.08},breakdown:{title:"Pending by Workflow",subtitle:"Items awaiting action",items:[["Leave approval",48],["Purchase indent",36],["Fee waiver",29],["Result moderation",24],["File movement",19]]},actions:[d("WFL-512","Escalation","17 steps past SLA","Escalate to next approver","Urgent","20 mins ago"),d("WFL-509","Delegation","HoD on leave for 5 days","Delegate approvals","Pending","2 hours ago"),d("WFL-503","Design","New hostel allotment flow","Review state machine","Review","Yesterday")],activity:[c("10:18 AM","Leave request approved","Department Admin","WFL-515"),c("09:44 AM","Purchase indent moved to finance","System","WFL-514"),c("Yesterday","Workflow version published","Admin","WFL-506")]},audit:{action:"Export Audit Log",kpis:[r("Events (30 days)","48,200","State-changing actions","+5.2%"),r("Modules writing","6","Sending audit events","muted","muted"),r("Admin actions","312","Super admin and org admin","+18"),r("Impersonation sessions","4","All audited","review","alert")],chart:{title:"Audit Events",subtitle:"Monthly, user vs system",series:["User","System"],base:42e3,split:.3},breakdown:{title:"Events by Service",subtitle:"Last 30 days",items:[["identity",18400],["tenancy",9200],["billing",6100],["workflow",8300],["documents",6200]]},actions:[d("AUD-210","Impersonation","Super admin session reviewed","Confirm reason recorded","Review","1 hour ago"),d("AUD-206","Retention","Retention policy to set","Decide retention period per event type","Pending","1 day ago"),d("AUD-201","Export","Quarterly audit export","For governance review","Pending","2 days ago")],activity:[c("10:42 AM","tenancy.impersonation.started","Super Admin","AUD-212"),c("10:11 AM","identity.user.created","Organisation Admin","AUD-211"),c("Yesterday","tenancy.entitlement.changed","Organisation Admin","AUD-208")]},notification:{action:"New Template",kpis:[r("Messages (30 days)","62,400","Email, SMS, WhatsApp, push, in-app","+12%"),r("Delivered","98.4%","Across channels","+0.6 pts"),r("Templates","84","Active templates","+6"),r("Failed","1,010","Bounced or undelivered","review","alert")],chart:{title:"Messages Sent",subtitle:"Monthly, delivered vs failed",series:["Delivered","Failed"],base:58e3,split:.02},breakdown:{title:"Messages by Channel",subtitle:"Last 30 days",items:[["Email",24800],["In-app",16200],["SMS",11400],["WhatsApp",7600],["Push",2400]]},actions:[d("NTF-140","Bounces","Email bounces from one domain","412 bounces since Monday","Urgent","1 hour ago"),d("NTF-137","Template","Fee reminder template","Approval of new wording","Pending","4 hours ago"),d("NTF-133","Opt-outs","SMS opt-out requests","26 requests to process","Review","Yesterday")],activity:[c("10:30 AM","Trial expiry reminder sent","System","NTF-143"),c("09:15 AM","Exam schedule broadcast","Examination Staff","NTF-142"),c("Yesterday","Template updated: hostel notice","Admin","NTF-139")]},documents:{action:"Upload Document",kpis:[r("Documents","1.86 L","Stored across modules","+4.1%"),r("Storage used","612 GB","Of plan limit","61%","muted"),r("Uploads (30 days)","9,840","New files and versions","+7.3%"),r("Access requests","23","Awaiting owner approval","review","alert")],chart:{title:"Uploads",subtitle:"Monthly, new files vs new versions",series:["New files","New versions"],base:8600,split:.3},breakdown:{title:"Storage by Module",subtitle:"GB used",items:[["Admissions",182],["Training & video",164],["Student information",96],["E-Office",88],["LMS",82]]},actions:[d("DOC-301","Access","23 access requests","Owners to approve or deny","Pending","2 hours ago"),d("DOC-298","Storage","Video storage growing fast","Review retention for raw footage","Review","5 hours ago"),d("DOC-294","Scan","Unreadable scanned certificates","41 files to re-scan","Urgent","Yesterday")],activity:[c("10:22 AM","New version of fee circular","Finance Staff","DOC-304"),c("09:48 AM","Batch upload: hall tickets","Examination Staff","DOC-303"),c("Yesterday","Folder permissions changed","Admin","DOC-299")]},reporting:{action:"New Report",kpis:[r("Reports","146","MIS and dashboards","+9"),r("Runs (30 days)","4,320","Scheduled and on demand","+14%"),r("Scheduled","38","Delivered by email","muted","muted"),r("Failed runs","12","Last 30 days","review","alert")],chart:{title:"Report Runs",subtitle:"Monthly, scheduled vs on demand",series:["Scheduled","On demand"],base:3900,split:.45},breakdown:{title:"Most Used Reports",subtitle:"Runs in the last 30 days",items:[["Attendance by department",620],["Fee collection",540],["Results summary",410],["Admissions funnel",380],["Hostel occupancy",210]]},actions:[d("RPT-077","Failure","Nightly fee report failed","Source data late","Urgent","1 hour ago"),d("RPT-074","Request","New NAAC criterion report","Requested by IQAC","Pending","6 hours ago"),d("RPT-070","Schedule","Weekly management pack","Recipients to confirm","Review","Yesterday")],activity:[c("10:01 AM","Attendance report generated","Department Admin","RPT-080"),c("08:30 AM","Management pack emailed","System","RPT-079"),c("Yesterday","Report definition updated","Admin","RPT-072")]},search:{action:"Rebuild Index",kpis:[r("Searches (30 days)","84,600","Across modules","+18%"),r("Indexed records","6.2 L","Students, files, notices, more","+3.4%"),r("Zero-result searches","4.1%","No match found","-0.8 pts"),r("Index lag","42 s","Average time to searchable","muted","muted")],chart:{title:"Searches",subtitle:"Monthly, found vs no result",series:["Found","No result"],base:78e3,split:.04},breakdown:{title:"Searches by Area",subtitle:"Last 30 days",items:[["Students",31200],["Documents",18400],["Notices",14600],["Courses",11200],["Staff",9200]]},actions:[d("SRC-021","Synonyms","Top zero-result terms","Add synonyms for 14 terms","Review","2 hours ago"),d("SRC-019","Index","Library catalogue not indexed","Connect once library is enabled","Pending","1 day ago"),d("SRC-016","Lag","Index lag spike","Investigate during peak","Urgent","Yesterday")],activity:[c("10:10 AM","Notices index refreshed","System","SRC-024"),c("09:00 AM","Synonym list updated","Admin","SRC-022"),c("Yesterday","Full re-index completed","System","SRC-018")]},scheduler:{action:"New Job",kpis:[r("Scheduled jobs","64","Cron and one-off","+5"),r("Runs (24 hours)","1,920","Jobs executed","+2.1%"),r("Success rate","99.2%","Last 7 days","+0.3 pts"),r("Failed runs","15","Last 7 days","review","alert")],chart:{title:"Job Runs",subtitle:"Monthly, succeeded vs failed",series:["Succeeded","Failed"],base:56e3,split:.01},breakdown:{title:"Jobs by Type",subtitle:"Active jobs",items:[["Reminders",22],["Report delivery",14],["Data sync",12],["Clean-up",9],["Alerts",7]]},actions:[d("SCH-061","Failure","Trial expiry job failed twice","Check retry settings","Urgent","1 hour ago"),d("SCH-058","New job","Daily attendance alert","Approve schedule","Pending","4 hours ago"),d("SCH-055","Overlap","Two jobs at 02:00","Stagger to reduce load","Review","Yesterday")],activity:[c("10:00 AM","Fee reminder job completed","System","SCH-064"),c("06:00 AM","Nightly clean-up completed","System","SCH-063"),c("Yesterday","Trial expiry job retried","System","SCH-060","Warning")]},"event-bus":{action:"View Contracts",kpis:[r("Events (24 hours)","1.12 L","Published between modules","+6.8%"),r("Event types","29","Defined in contracts/events.yaml","+6"),r("Consumers","11","Subscribed modules","muted","muted"),r("Dead letters","18","Failed after retries","review","alert")],chart:{title:"Events Published",subtitle:"Monthly, delivered vs retried",series:["Delivered","Retried"],base:32e5,split:.02},breakdown:{title:"Events by Publisher",subtitle:"Last 24 hours",items:[["identity",38200],["tenancy",24600],["billing",18300],["workflow",17900],["notification",13e3]]},actions:[d("EVB-033","Dead letters","18 events failed delivery","Inspect and replay","Urgent","45 mins ago"),d("EVB-030","Contract","New event type proposed","training-video-analysis.video.tagged","Review","3 hours ago"),d("EVB-027","Consumer","Slow consumer lag","Reporting consumer behind by 4 min","Pending","Yesterday")],activity:[c("10:35 AM","tenancy.entitlement.changed delivered","System","EVB-036"),c("10:02 AM","billing.subscription.started delivered","System","EVB-035"),c("Yesterday","Dead-letter replay completed","Admin","EVB-029")]},"integration-hub":{action:"Add Adapter",kpis:[r("Adapters","8","Registered integrations","muted","muted"),r("Exchanges (30 days)","24,600","XML, JSON and CSV files","+9.5%"),r("Webhooks","14","Inbound endpoints","+2"),r("Failed exchanges","37","Retry queue","review","alert")],chart:{title:"Data Exchanges",subtitle:"Monthly, succeeded vs retried",series:["Succeeded","Retried"],base:22e3,split:.05},breakdown:{title:"Exchanges by Adapter",subtitle:"Last 30 days",items:[["Email / SMS / WhatsApp",11200],["SBIePay",5400],["DigiLocker",3100],["Government portals",2600],["Video conferencing",2300]]},actions:[d("INT-052","Retry","37 exchanges in retry queue","Government portal timeouts","Urgent","1 hour ago"),d("INT-049","Credentials","API key rotation due","Payment gateway key expires soon","Pending","5 hours ago"),d("INT-046","Mapping","AISHE CSV mapping change","Review new column layout","Review","Yesterday")],activity:[c("10:20 AM","DigiLocker batch exchanged","System","INT-055"),c("09:30 AM","Webhook endpoint added","Admin","INT-054"),c("Yesterday","Retry batch processed","System","INT-050","Warning")]},"api-gateway":{action:"View Routes",kpis:[r("Requests (24 hours)","3.4 L","Through the gateway","+7.2%"),r("Routes","126","Across modules","+14"),r("p95 latency","186 ms","Last 24 hours","-12 ms"),r("Rejected requests","2,140","Outside entitlement or rate limit","review","alert")],chart:{title:"Requests",subtitle:"Monthly, allowed vs rejected",series:["Allowed","Rejected"],base:96e5,split:.01},breakdown:{title:"Requests by Service",subtitle:"Last 24 hours",items:[["identity",112e3],["tenancy",64e3],["admissions",58e3],["lms",52e3],["billing",54e3]]},actions:[d("GTW-071","Rate limit","One client hitting limits","Raise limit or contact organisation","Review","1 hour ago"),d("GTW-068","Route","New module routes to publish","Skill progress API","Pending","6 hours ago"),d("GTW-064","Latency","p95 spike at 09:00","Investigate peak load","Urgent","Yesterday")],activity:[c("10:45 AM","Route table reloaded","System","GTW-074"),c("09:05 AM","Rate limit raised for one organisation","Admin","GTW-073"),c("Yesterday","Entitlement rejections reviewed","Admin","GTW-066")]},"payment-sbiepay":{action:"Test Connection",kpis:[r("Transactions (30 days)","8,420","Initiated through SBIePay","+11%"),r("Collected","₹4.86 Cr","Successful payments","+9.6%"),r("Success rate","97.8%","Paid on first attempt","+0.4 pts"),r("To reconcile","36","Callback without settlement","review","alert")],chart:{title:"Payments",subtitle:"Monthly, successful vs failed",series:["Successful","Failed"],base:7800,split:.03},breakdown:{title:"Payments by Purpose",subtitle:"Last 30 days",items:[["Tuition fees",5120],["Hostel fees",1640],["Application fees",980],["Event registrations",480],["Fines",200]]},actions:[d("PAY-301","Reconcile","36 payments not settled","Match against settlement file","Urgent","1 hour ago"),d("PAY-298","Refund","Duplicate payment refund","Finance approval needed","Pending","4 hours ago"),d("PAY-294","Config","Merchant key rotation","Due this month","Review","Yesterday")],activity:[c("10:28 AM","Payment callback received","SBIePay","PAY-305"),c("06:00 AM","Settlement file reconciled","System","PAY-304"),c("Yesterday","Payment failed: bank timeout","SBIePay","PAY-300","Failed")]},digilocker:{action:"Test Connection",kpis:[r("Certificates issued","3,260","Pushed to DigiLocker","+18%"),r("Verifications","1,140","Documents fetched from students","+9.2%"),r("Pending issue","84","Awaiting signature","review","alert"),r("Success rate","99.1%","Issue and fetch","+0.2 pts")],chart:{title:"DigiLocker Activity",subtitle:"Monthly, issued vs verified",series:["Issued","Verified"],base:820,split:.35},breakdown:{title:"Documents by Type",subtitle:"This year",items:[["Degree certificates",1420],["Marksheets",1180],["Migration certificates",360],["Transfer certificates",300]]},actions:[d("DGL-041","Signature","84 certificates to sign","Controller of Examinations","Urgent","2 hours ago"),d("DGL-038","Mismatch","Name mismatch on 6 records","Correct before issue","Pending","5 hours ago"),d("DGL-035","Batch","Convocation batch ready","Review before push","Review","Yesterday")],activity:[c("10:14 AM","Marksheets pushed to DigiLocker","System","DGL-044"),c("09:20 AM","Applicant document fetched","Admissions","DGL-043"),c("Yesterday","Issue failed: invalid Aadhaar link","DigiLocker","DGL-040","Failed")]},nad:{action:"Test Connection",kpis:[r("Records lodged","2,940","Academic awards on NAD","+14%"),r("Pending lodging","128","Results not yet sent","review","alert"),r("Verification requests","410","From employers and institutions","+22%"),r("Success rate","98.6%","Lodge and verify","+0.5 pts")],chart:{title:"NAD Records",subtitle:"Monthly, lodged vs verified",series:["Lodged","Verified"],base:620,split:.3},breakdown:{title:"Records by Programme",subtitle:"This year",items:[["Undergraduate",1680],["Postgraduate",820],["Diploma",290],["Doctoral",150]]},actions:[d("NAD-022","Lodging","128 results pending","Semester results to lodge","Urgent","3 hours ago"),d("NAD-019","Correction","Record correction request","Grade change approved","Pending","1 day ago"),d("NAD-016","Mapping","Programme codes update","Match new NAD codes","Review","2 days ago")],activity:[c("10:00 AM","Results batch lodged","System","NAD-025"),c("Yesterday","Employer verification answered","NAD","NAD-024"),c("Yesterday","Lodging failed: missing roll number","NAD","NAD-021","Failed")]},"government-portals":{action:"Test Connection",kpis:[r("Submissions (this year)","24","UGC, AISHE, NAAC and others","+5"),r("Due in 30 days","4","Statutory returns","1 overdue","alert"),r("Accepted","19","Acknowledged by portal","79%"),r("Data checks failed","7","Before submission","review","alert")],chart:{title:"Portal Submissions",subtitle:"Monthly, accepted vs returned",series:["Accepted","Returned"],base:4,split:.2},breakdown:{title:"Submissions by Portal",subtitle:"This year",items:[["AISHE",6],["UGC",7],["NAAC",4],["NIRF",3],["State government",4]]},actions:[d("GOV-017","Overdue","AISHE return overdue","Faculty data incomplete","Urgent","2 hours ago"),d("GOV-014","Data check","7 validation errors","Fix before UGC upload","Pending","1 day ago"),d("GOV-011","NIRF","NIRF data capture","Review draft figures","Review","2 days ago")],activity:[c("09:40 AM","UGC return acknowledged","UGC portal","GOV-020"),c("Yesterday","NAAC data uploaded","IQAC","GOV-019"),c("Yesterday","AISHE upload rejected","AISHE portal","GOV-016","Failed")]},"messaging-providers":{action:"Test Connection",kpis:[r("Messages (30 days)","45,200","Email, SMS and WhatsApp","+12%"),r("Delivery rate","98.1%","Across providers","+0.4 pts"),r("Providers","3","Email, SMS, WhatsApp","muted","muted"),r("Provider errors","860","Last 30 days","review","alert")],chart:{title:"Messages Sent",subtitle:"Monthly, delivered vs failed",series:["Delivered","Failed"],base:42e3,split:.02},breakdown:{title:"Messages by Provider",subtitle:"Last 30 days",items:[["Email",24800],["SMS",11400],["WhatsApp",9e3]]},actions:[d("MSG-029","Errors","SMS provider timeouts","312 retries since morning","Urgent","1 hour ago"),d("MSG-026","Template","WhatsApp template approval","Waiting for provider approval","Pending","6 hours ago"),d("MSG-023","Domain","Email sender domain check","Review sending domain settings","Review","Yesterday")],activity:[c("10:32 AM","Batch sent: fee reminders","System","MSG-032"),c("09:12 AM","Provider failover to backup SMS","System","MSG-031","Warning"),c("Yesterday","WhatsApp template approved","Provider","MSG-028")]},"video-conferencing":{action:"Test Connection",kpis:[r("Meetings (30 days)","1,860","Online classes and meetings","+15%"),r("Hours hosted","3,420","Total meeting time","+12%"),r("Recordings","1,140","Saved to documents","+9%"),r("Join failures","46","Last 30 days","review","alert")],chart:{title:"Meetings Hosted",subtitle:"Monthly, classes vs meetings",series:["Classes","Meetings"],base:1700,split:.3},breakdown:{title:"Meetings by Platform",subtitle:"Last 30 days",items:[["Zoom",820],["Microsoft Teams",640],["Webex",400]]},actions:[d("VC-038","Licences","Licence limit near","92% of hosts in use","Urgent","2 hours ago"),d("VC-035","Recording","Recordings not synced","14 recordings pending upload","Pending","5 hours ago"),d("VC-031","Settings","Waiting room policy","Review for exams","Review","Yesterday")],activity:[c("10:00 AM","Class meeting created from timetable","System","VC-041"),c("09:30 AM","Recording saved","System","VC-040"),c("Yesterday","Join failed: expired link","Zoom","VC-037","Failed")]},wearables:{action:"Test Connection",kpis:[r("Connected devices","412","Athlete wearables","+38"),r("Readings (7 days)","1.8 L","Heart rate, load, sleep","+11%"),r("Athletes covered","96%","Of active athletes","+4 pts"),r("High-load alerts","23","Last 7 days","review","alert")],chart:{title:"Readings Received",subtitle:"Monthly, training vs recovery",series:["Training","Recovery"],base:7e5,split:.4},breakdown:{title:"Devices by Sport",subtitle:"Connected devices",items:[["Athletics",128],["Football",96],["Hockey",74],["Wrestling",62],["Swimming",52]]},actions:[d("WRB-027","Alert","23 high-load alerts","Coaches to review training load","Urgent","40 mins ago"),d("WRB-024","Sync","18 devices not synced","No data for 3 days","Pending","4 hours ago"),d("WRB-021","Consent","Data consent renewals","Athletes to re-confirm","Review","Yesterday")],activity:[c("10:20 AM","Overnight recovery data synced","System","WRB-030"),c("08:45 AM","High-load alert raised","System","WRB-029","Warning"),c("Yesterday","New devices paired","Coach","WRB-026")]},"external-university-portals":{action:"Test Connection",kpis:[r("Partner institutions","14","Connected portals","+2"),r("Exchanges (30 days)","1,260","Credits, transcripts, enrolments","+16%"),r("Credit transfers","184","Processed this term","+28"),r("Failed exchanges","9","Last 30 days","review","alert")],chart:{title:"Data Exchanges",subtitle:"Monthly, sent vs received",series:["Sent","Received"],base:1100,split:.45},breakdown:{title:"Exchanges by Type",subtitle:"Last 30 days",items:[["Transcripts",520],["Credit transfers",340],["Enrolment checks",260],["Exchange students",140]]},actions:[d("EXT-015","Credit","12 credit transfers to approve","From partner university","Pending","3 hours ago"),d("EXT-012","Failure","Transcript exchange failed","Partner portal unavailable","Urgent","5 hours ago"),d("EXT-009","Partner","New partner onboarding","Agree data format","Review","Yesterday")],activity:[c("10:05 AM","Transcripts sent to partner","System","EXT-018"),c("Yesterday","Credit transfer received","Partner portal","EXT-017"),c("Yesterday","Exchange failed: timeout","Partner portal","EXT-014","Failed")]}};function vc(t){const n=t.kind==="integration";return{action:n?"Test Connection":"Open Settings",kpis:n?[r("Requests (30 days)","18,420","Calls through the adapter","+7%"),r("Success rate","99.2%","Responses without error","healthy"),r("Failed calls","146","Retried by integration hub","review","alert"),r("Avg. latency","420 ms","Round trip","-30 ms")]:[r("Requests (30 days)","2.4 L","From all modules","+11%"),r("Availability","99.97%","Last 30 days","SLA met"),r("Errors","38","Logged this month","review","alert"),r("Modules using it","36","Through packages/sdk","all")],chart:{title:"Requests",subtitle:"Monthly, successful vs retried",series:["Successful","Retried"],base:n?3e3:4e4,split:.04},breakdown:{title:"Top Callers",subtitle:"Requests this month",items:[["Admissions",4200],["Fees & Accounts",3600],["Examinations",2900],["Student Information",2100],["Helpdesk",1300]]},actions:[d(`${t.id.toUpperCase().slice(0,6)}-01`,"Configuration",`Review ${t.name} configuration`,"Keys listed in config/env.example","Review","2 hours ago"),d(`${t.id.toUpperCase().slice(0,6)}-02`,"Errors","Recurring errors this week","Inspect logs in monitoring","Pending","Yesterday")],activity:[c("10:00 AM","Health check passed","Monitoring",`${t.id}-HC`),c("Yesterday","Configuration reloaded","System",`${t.id}-CFG`)]}}const wc=["Apr","May","Jun","Jul","Aug","Sep"];function $s(t,n,s=0){let a=[...t].reduce((o,m)=>o*31+m.charCodeAt(0)>>>0,7);const i=()=>(a=a*1664525+1013904223>>>0,a/2**32);return wc.map((o,m)=>{const p=.82+m*.05,h=Math.max(1,Math.round(n*p*(.85+i()*.3))),u=Math.round(h*s);return{month:o,a:h-u,b:u}})}const Ee=Is.admissions,kc=()=>{const[t,n]=f.useState(gd),[s,a]=f.useState(!1);f.useEffect(()=>{const j=new Image;j.onload=()=>a(!0),j.src=O("/admissions.jpg")},[]);const[i,o]=f.useState(""),[m,p]=f.useState("All"),[h,u]=f.useState("All"),[v,g]=f.useState("All"),[l,x]=f.useState(null),[w,N]=f.useState(!1),[b,S]=f.useState(null),E=j=>{S(j),setTimeout(()=>S(null),3500)},y=j=>{x(j),N(!0)},k=()=>{N(!1),x(null)},B=j=>{n(P=>P.map(R=>{if(R.id===j){const _={...R,status:"Confirmed",timeline:R.timeline.map(D=>D.step==="Document Verification"?{...D,status:"completed",note:"Statutory verification signed off by Admissions Committee"}:D.step==="Confirmation & Registration"?{...D,status:"completed",timestamp:"Just now",note:"Marked confirmed (sample)"}:D)};return(l==null?void 0:l.id)===j&&x(_),_}return R})),E(`Sample only: ${j} marked Confirmed on this page. No letter is sent; the admissions module is not built yet.`)},T=j=>{n(P=>P.map(R=>{if(R.id===j){const _={...R,status:"Under Review",timeline:R.timeline.map(D=>D.step==="Document Verification"?{...D,status:"in-progress",note:"Changes requested (sample)"}:D)};return(l==null?void 0:l.id)===j&&x(_),_}return R})),E(`Sample only: ${j} sent back to review on this page. No message is sent to the candidate.`)},C=j=>{if(!l)return;const P=l.documents.map(_=>_.id===j?{..._,verified:!_.verified}:_),R={...l,documents:P};x(R),n(_=>_.map(D=>D.id===R.id?R:D))},M=t.filter(j=>{const P=j.applicant.toLowerCase().includes(i.toLowerCase())||j.id.toLowerCase().includes(i.toLowerCase())||j.email.toLowerCase().includes(i.toLowerCase()),R=m==="All"||j.status===m,_=h==="All"||j.programme.includes(h),D=v==="All"||j.category===v;return P&&R&&_&&D});return e.jsxs(Bs,{theme:Ds("student-lifecycle"),className:"space-y-6",children:[b&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs",children:[e.jsx(z,{className:"w-4 h-4 text-[#126B3D]"}),e.jsx("span",{children:b})]}),e.jsx(me,{title:"Admissions",art:s?e.jsx(Gt,{src:O("/admissions.jpg"),position:"70% 45%",tone:"violet"}):void 0,subtitle:"Application and verification workflow · Academic Year 2026–27",actions:e.jsxs("button",{onClick:()=>E("Export needs the admissions module, which is not built yet"),className:se,children:[e.jsx(Tt,{className:"w-3.5 h-3.5 text-[#475569]"}),"Export Roster"]})}),e.jsx(ce,{stats:[{label:"Total applications",icon:qe,value:"1,284",note:"Undergraduate & Masters"},{label:"Confirmed",icon:z,value:"486",delta:"37.8%",note:"Sample figure"},{label:"Under review",icon:Ke,value:"86",delta:"Dean review",deltaTone:"alert",note:"Requires Dean review"},{label:"Shortlisted",icon:Qe,value:"824",delta:"64.2%",deltaTone:"muted",note:"Counselling invitations issued"}]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsx(zt,{className:"lg:col-span-2",title:Ee.chart.title,subtitle:Ee.chart.subtitle,data:$s("admissions",Ee.chart.base,Ee.chart.split),xKey:"month",series:[{key:"a",name:Ee.chart.series[0]},{key:"b",name:Ee.chart.series[1]}],tooltipLabel:j=>`${j} 2026`}),e.jsx(Kt,{title:"Admissions Funnel",subtitle:"Batch 2026 conversion",relativeToFirst:!0,items:ms.map((j,P)=>({label:j.stage,count:j.count,color:cs[P]})),footer:{label:"Overall acceptance",value:"37.8%"}})]}),e.jsx("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs",children:e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3",children:[e.jsxs("div",{className:"relative",children:[e.jsx(he,{className:"w-4 h-4 text-[#475569] absolute left-3 top-2.5"}),e.jsx("input",{type:"text",placeholder:"Search by candidate name or ID...",value:i,onChange:j=>o(j.target.value),className:"w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"})]}),e.jsx("div",{children:e.jsxs("select",{value:m,onChange:j=>p(j.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Statuses"}),e.jsx("option",{value:"Under Review",children:"Under Review"}),e.jsx("option",{value:"Shortlisted",children:"Shortlisted"}),e.jsx("option",{value:"Confirmed",children:"Confirmed"})]})}),e.jsx("div",{children:e.jsxs("select",{value:h,onChange:j=>u(j.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Programmes"}),e.jsx("option",{value:"B.Tech",children:"B.Tech CSE (Sports Analytics)"}),e.jsx("option",{value:"B.Sc",children:"B.Sc Sports Science & Biomechanics"}),e.jsx("option",{value:"BBA",children:"BBA Sports Management"}),e.jsx("option",{value:"M.P.Ed",children:"M.P.Ed Physical Education"})]})}),e.jsx("div",{children:e.jsxs("select",{value:v,onChange:j=>g(j.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Categories"}),e.jsx("option",{value:"General",children:"General"}),e.jsx("option",{value:"OBC",children:"OBC"}),e.jsx("option",{value:"SC/ST",children:"SC/ST"}),e.jsx("option",{value:"Sports Quota",children:"Sports Quota"}),e.jsx("option",{value:"Defence",children:"Defence"})]})})]})}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden",children:[e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-3 px-4",children:"Application ID"}),e.jsx("th",{className:"py-3 px-4",children:"Applicant"}),e.jsx("th",{className:"py-3 px-4",children:"Programme"}),e.jsx("th",{className:"py-3 px-4",children:"Category"}),e.jsx("th",{className:"py-3 px-4",children:"Status"}),e.jsx("th",{className:"py-3 px-4",children:"Submitted"}),e.jsx("th",{className:"py-3 px-4 text-right",children:"Action"})]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9] text-[#12233F]",children:M.length===0?e.jsx("tr",{children:e.jsx("td",{colSpan:7,className:"py-8 text-center text-[#475569]",children:"No applicant records match the selected filters."})}):M.map(j=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors cursor-pointer group",onClick:()=>y(j),children:[e.jsx("td",{className:"py-3 px-4 font-mono font-medium text-[var(--accent)]",children:j.id}),e.jsxs("td",{className:"py-3 px-4",children:[e.jsx("div",{className:"font-semibold text-[#12233F]",children:j.applicant}),e.jsxs("div",{className:"text-[11px] text-[#64748B] flex items-center gap-1",children:[e.jsxs("span",{children:["Rank #",j.meritRank]}),j.sportsDiscipline&&e.jsxs("span",{children:["• ",j.sportsDiscipline]})]})]}),e.jsx("td",{className:"py-3 px-4 text-[#12233F] font-medium",children:j.programme}),e.jsx("td",{className:"py-3 px-4",children:e.jsx("span",{className:"px-2 py-0.5 rounded text-[10px] font-medium bg-[#F1F5F9] text-[var(--accent)]",children:j.category})}),e.jsx("td",{className:"py-3 px-4",children:e.jsxs("span",{className:`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${j.status==="Confirmed"?"bg-[#16834B26] text-[#126B3D]":j.status==="Shortlisted"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-current"}),j.status]})}),e.jsx("td",{className:"py-3 px-4 text-[#475569]",children:j.submitted}),e.jsx("td",{className:"py-3 px-4 text-right",onClick:P=>P.stopPropagation(),children:e.jsx("button",{onClick:()=>y(j),className:"px-3 py-1 rounded-md border border-[#E2E8F0] hover:border-[#9333EA] text-[var(--accent)] font-semibold hover:bg-[#FFFFFF] text-[11px] transition-colors",children:"View →"})})]},j.id))})]})}),e.jsxs("div",{className:"py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]",children:[e.jsxs("span",{children:["Displaying ",e.jsx("strong",{className:"text-[#12233F]",children:M.length})," candidate applications"]}),e.jsx("span",{className:"text-[11px]",children:"Sample data · admissions module not built yet"})]})]}),w&&l&&e.jsxs("div",{className:"fixed inset-0 z-50 overflow-hidden",children:[e.jsx("div",{className:"absolute inset-0 bg-[#12233F]/50 backdrop-blur-xs transition-opacity",onClick:k}),e.jsx("div",{className:"fixed inset-y-0 right-0 max-w-full flex pl-10",children:e.jsxs("div",{className:"w-screen max-w-lg bg-[#FFFFFF] shadow-2xl border-l border-[#E2E8F0] flex flex-col",children:[e.jsxs("div",{className:"p-5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]",children:[e.jsxs("div",{className:"flex items-center gap-2",children:[e.jsx("span",{className:"font-mono text-xs px-2 py-0.5 rounded bg-[#7E22CE26] text-[var(--accent)] font-bold",children:l.id}),e.jsx("span",{className:"text-sm font-bold text-[#12233F]",children:"APPLICATION DETAILS"})]}),e.jsx("button",{onClick:k,className:"p-1 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#FFFFFF]",children:e.jsx(ae,{className:"w-5 h-5"})})]}),e.jsxs("div",{className:"flex-1 overflow-y-auto p-6 space-y-6",children:[e.jsxs("div",{className:"p-4 rounded-xl bg-[#F6F8FB] border border-[#E2E8F0] space-y-3",children:[e.jsxs("div",{className:"flex items-start justify-between",children:[e.jsxs("div",{children:[e.jsx("h3",{className:"text-base font-bold text-[#12233F]",children:l.applicant}),e.jsx("p",{className:"text-xs text-[var(--accent)] font-medium",children:l.programme})]}),e.jsx("span",{className:`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${l.status==="Confirmed"?"bg-[#16834B26] text-[#126B3D]":l.status==="Shortlisted"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:l.status})]}),e.jsxs("div",{className:"grid grid-cols-2 gap-2 text-xs pt-2 border-t border-[#E2E8F0]",children:[e.jsxs("div",{children:[e.jsx("span",{className:"text-[#475569] text-[11px]",children:"Quota / Category:"}),e.jsx("p",{className:"font-semibold text-[#12233F]",children:l.category})]}),e.jsxs("div",{children:[e.jsx("span",{className:"text-[#475569] text-[11px]",children:"Merit Rank:"}),e.jsxs("p",{className:"font-semibold text-[#12233F]",children:["Merit Rank #",l.meritRank]})]}),e.jsxs("div",{children:[e.jsx("span",{className:"text-[#475569] text-[11px]",children:"Candidate Contact:"}),e.jsx("p",{className:"font-mono text-[#12233F]",children:l.phone})]}),e.jsxs("div",{children:[e.jsx("span",{className:"text-[#475569] text-[11px]",children:"Email Address:"}),e.jsx("p",{className:"font-mono text-[var(--accent)] truncate",children:l.email})]})]}),l.sportsDiscipline&&e.jsxs("div",{className:"pt-2 border-t border-[#E2E8F0] flex items-center gap-1.5 text-xs text-[var(--accent)]",children:[e.jsx(Ti,{className:"w-3.5 h-3.5 text-[#8A4F00]"}),e.jsx("span",{className:"font-medium",children:"Athletic Discipline:"}),e.jsx("span",{className:"font-semibold",children:l.sportsDiscipline})]})]}),e.jsxs("div",{className:"space-y-3",children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsxs("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider",children:["Uploaded Statutory Documents (",l.documents.length,")"]}),e.jsx("span",{className:"text-[11px] text-[#475569]",children:"Click checkbox to toggle verification"})]}),e.jsx("div",{className:"space-y-2",children:l.documents.map(j=>e.jsxs("div",{onClick:()=>C(j.id),className:`p-3 rounded-lg border flex items-center justify-between transition-colors cursor-pointer ${j.verified?"bg-[#16834B26]/30 border-[#16834B]/30 hover:bg-[#16834B26]/50":"bg-[#DC262614] border-[#DC262640] hover:bg-[#DC262626]"}`,children:[e.jsxs("div",{className:"flex items-center gap-2.5",children:[e.jsx("button",{type:"button",className:`w-5 h-5 rounded flex items-center justify-center transition-colors ${j.verified?"bg-[#16834B] text-white":"border border-[#CBD5E1] bg-[#FFFFFF]"}`,children:j.verified&&e.jsx(Ve,{className:"w-3.5 h-3.5 stroke-[3]"})}),e.jsxs("div",{children:[e.jsx("p",{className:"text-xs font-semibold text-[#12233F]",children:j.name}),e.jsxs("p",{className:"text-[10px] text-[#475569]",children:["Format: ",j.type," • ",j.fileSize||"size unknown"]})]})]}),e.jsx("span",{className:`text-[10px] font-semibold px-2 py-0.5 rounded ${j.verified?"bg-[#16834B26] text-[#126B3D]":"bg-[#DC262626] text-[#B91C1C]"}`,children:j.verified?"Verified ✓":"Pending Verification"})]},j.id))})]}),e.jsxs("div",{className:"space-y-3",children:[e.jsx("h4",{className:"text-xs font-bold text-[#12233F] uppercase tracking-wider",children:"Application Lifecycle Timeline"}),e.jsx("div",{className:"relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#E2E8F0]",children:l.timeline.map((j,P)=>{const R=j.status==="completed",_=j.status==="in-progress";return e.jsxs("div",{className:"relative",children:[e.jsx("div",{className:`absolute -left-6 top-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center ${R?"bg-[#16834B] border-white text-white":_?"bg-[#9333EA] border-white text-white animate-pulse":"bg-[#F1F5F9] border-[#CBD5E1]"}`,children:R&&e.jsx(Ve,{className:"w-2.5 h-2.5 stroke-[3]"})}),e.jsxs("div",{className:"space-y-0.5",children:[e.jsx("p",{className:"text-xs font-bold text-[#12233F]",children:j.step}),e.jsx("p",{className:"text-[11px] text-[#475569]",children:j.timestamp}),j.note&&e.jsx("p",{className:"text-[11px] text-[var(--accent)] bg-[#7E22CE26]/40 p-1.5 rounded mt-1",children:j.note})]})]},P)})})]})]}),e.jsxs("div",{className:"p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] space-y-2",children:[e.jsxs("div",{className:"grid grid-cols-2 gap-2",children:[e.jsxs("button",{onClick:()=>T(l.id),className:"py-2.5 px-3 rounded-lg border border-[#F39A19] text-[#8A4F00] hover:bg-[#F39A1926]/40 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5",children:[e.jsx(Ye,{className:"w-3.5 h-3.5"}),e.jsx("span",{children:"Request Changes"})]}),e.jsxs("button",{onClick:()=>B(l.id),disabled:l.status==="Confirmed",className:"py-2.5 px-3 rounded-lg bg-[#16834B] hover:bg-[#126B3D] text-white text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-sm disabled:opacity-70",children:[e.jsx(z,{className:"w-3.5 h-3.5"}),e.jsx("span",{children:"Approve & Admit"})]})]}),e.jsx("p",{className:"text-[10px] text-center text-[#475569]",children:"Sample workflow: changes stay on this page. The admissions module is not built yet."})]})]})})]})]})},jc=()=>{const[t]=f.useState(ds),[n,s]=f.useState(""),[a,i]=f.useState("All"),[o,m]=f.useState("All"),[p,h]=f.useState(null),u=l=>{h(l),setTimeout(()=>h(null),3e3)},v=t.filter(l=>{const x=l.user.toLowerCase().includes(n.toLowerCase())||l.action.toLowerCase().includes(n.toLowerCase())||l.resource.toLowerCase().includes(n.toLowerCase()),w=a==="All"||l.role===a,N=o==="All"||l.status===o;return x&&w&&N}),g=["All",...Array.from(new Set(t.map(l=>l.role)))];return e.jsxs("div",{className:"space-y-6",children:[p&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs",children:[e.jsx(z,{className:"w-4 h-4 text-[#126B3D]"}),e.jsx("span",{children:p})]}),e.jsx(me,{title:"Audit Activity",subtitle:e.jsxs("span",{className:"inline-flex flex-wrap items-center gap-2",children:["Every state change writes to platform/audit, and audit records are immutable (ARCHITECTURE.md). Its API is not built yet, so these are sample events using the event names in the repo's contracts.",e.jsxs("span",{className:"inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#475569]",children:[e.jsx(He,{className:"w-3 h-3"}),"Sample data"]})]}),actions:e.jsx(e.Fragment,{children:e.jsxs("button",{onClick:()=>u("Export needs the platform/audit API, which is not built yet"),className:Fe,children:[e.jsx(Tt,{className:"w-3.5 h-3.5"}),"Export Audit Log"]})})}),e.jsx(ce,{stats:[{label:"Events today",icon:qn,value:String(t.filter(l=>!l.timestamp.startsWith("Yesterday")).length),note:"Sample events"},{label:"Successful",icon:z,value:String(t.filter(l=>l.status==="Success").length),note:"State changes recorded"},{label:"Blocked or failed",icon:Kn,value:String(t.filter(l=>l.status!=="Success").length),delta:"review",deltaTone:"alert",note:"Failed or needs review"},{label:"Active actors",icon:Qe,value:String(new Set(t.map(l=>l.user)).size),note:"Distinct users and services"}]}),e.jsx("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs",children:e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-3 gap-3",children:[e.jsxs("div",{className:"relative",children:[e.jsx(he,{className:"w-4 h-4 text-[#475569] absolute left-3 top-2.5"}),e.jsx("input",{type:"text",placeholder:"Search by action, user, or resource ID...",value:n,onChange:l=>s(l.target.value),className:"w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"})]}),e.jsx("div",{children:e.jsxs("select",{value:a,onChange:l=>i(l.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Roles"}),g.filter(l=>l!=="All").map(l=>e.jsx("option",{value:l,children:J(l)},l))]})}),e.jsx("div",{children:e.jsxs("select",{value:o,onChange:l=>m(l.target.value),className:"w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]",children:[e.jsx("option",{value:"All",children:"All Event Outcomes"}),e.jsx("option",{value:"Success",children:"Success"}),e.jsx("option",{value:"Failed",children:"Failed"}),e.jsx("option",{value:"Warning",children:"Warning"})]})})]})}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden",children:[e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-left border-collapse text-xs",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold",children:[e.jsx("th",{className:"py-3 px-4 w-32",children:"Timestamp"}),e.jsx("th",{className:"py-3 px-4",children:"User"}),e.jsx("th",{className:"py-3 px-4",children:"Role"}),e.jsx("th",{className:"py-3 px-4",children:"Action"}),e.jsx("th",{className:"py-3 px-4",children:"Resource Target"}),e.jsx("th",{className:"py-3 px-4",children:"Status"}),e.jsx("th",{className:"py-3 px-4 text-right",children:"Origin IP"})]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9] text-[#12233F]",children:v.length===0?e.jsx("tr",{children:e.jsx("td",{colSpan:7,className:"py-8 text-center text-[#475569]",children:"No audit records matching search parameters."})}):v.map(l=>e.jsxs("tr",{className:"hover:bg-[#F6F8FB] transition-colors",children:[e.jsx("td",{className:"py-3 px-4 font-mono text-[#475569] whitespace-nowrap",children:l.timestamp}),e.jsx("td",{className:"py-3 px-4 font-semibold text-[#12233F]",children:l.user}),e.jsx("td",{className:"py-3 px-4",children:e.jsx("span",{className:"px-2 py-0.5 rounded text-[10px] font-medium bg-[#F1F5F9] text-[#7E22CE]",children:J(l.role)})}),e.jsx("td",{className:"py-3 px-4 text-[#12233F]",children:l.action}),e.jsx("td",{className:"py-3 px-4 font-mono text-[#7E22CE] font-semibold",children:l.resource}),e.jsx("td",{className:"py-3 px-4",children:e.jsxs("span",{className:`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${l.status==="Success"?"bg-[#16834B26] text-[#126B3D]":l.status==="Warning"?"bg-[#F39A1926] text-[#8A4F00]":"bg-[#DC262626] text-[#B91C1C]"}`,children:[l.status==="Success"?e.jsx(z,{className:"w-3 h-3"}):l.status==="Warning"?e.jsx(Ye,{className:"w-3 h-3"}):e.jsx(es,{className:"w-3 h-3"}),e.jsx("span",{children:l.status})]})}),e.jsx("td",{className:"py-3 px-4 text-right font-mono text-[11px] text-[#64748B]",children:l.ipAddress})]},l.id))})]})}),e.jsxs("div",{className:"py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]",children:[e.jsxs("span",{children:["Displaying ",e.jsx("strong",{className:"text-[#12233F]",children:v.length})," sequential ledger entries"]}),e.jsx("span",{className:"text-[11px]",children:"platform/audit: append-only by design; API not built yet"})]})]})]})},Fn={planned:"bg-[#F1F5F9] text-[#475569]","in-progress":"bg-[#F39A1926] text-[#8A4F00]",stable:"bg-[#16834B26] text-[#126B3D]",deprecated:"bg-[#F1F5F9] text-[#64748B]"},Vs={included:"bg-[#16834B26] text-[#126B3D]",upgrade:"bg-[#F39A1926] text-[#8A4F00]","not-in-profile":"bg-[#F1F5F9] text-[#64748B]",platform:"bg-[#7E22CE26] text-[#7E22CE]","per-organisation":"bg-[#F1F5F9] text-[#475569]"};function Fc(t){if(!t.entitlement||!t.profile)return`# Super admin: outside every organisation.
# Each organisation's entitlement =
#   academy profile modules ∩ plan (∪ overrides)
`;const n=[...t.entitlement.modules],s=a=>a.length?a.map(i=>`
  - ${i}`).join(""):" []";return`# entitlement = profile modules ∩ plan (∪ overrides)
academy_type: ${t.profile.profile}
plan: ${t.entitlement.plan}
modules:${s(n)}
upgrade_to_unlock:${s(t.entitlement.upgradableModules)}
`}const Nc=()=>{var u,v;const t=ye(),[n,s]=f.useState(""),a=n.trim().toLowerCase(),i=g=>!a||g.name.toLowerCase().includes(a)||g.id.includes(a),o=[...fe.map(g=>({key:g.id,title:vt(g),path:`modules/${g.domain}/`,modules:g.modules})),{key:"platform",title:"Shared platform services",path:"platform/",modules:Ce},{key:"integrations",title:"External integrations",path:"integrations/",modules:Te}].map(g=>({...g,modules:g.modules.filter(i)})).filter(g=>g.modules.length),m=fe.flatMap(g=>g.modules),p=m.filter(g=>Re(g,t)==="included").length,h=qt.filter(g=>g.implemented);return e.jsxs("div",{className:"space-y-6",children:[e.jsx(me,{title:"Module Registry",subtitle:"Every module in the monorepo. An organisation may use the modules in its academy profile and plan (its entitlement); a super admin can add overrides.",actions:e.jsxs("div",{className:"relative",children:[e.jsx(he,{className:"w-3.5 h-3.5 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2"}),e.jsx("input",{value:n,onChange:g=>s(g.target.value),placeholder:"Search modules",className:"h-8 pl-8 pr-3 w-56 rounded-full bg-[#F1F5F9] text-xs text-[#12233F] placeholder:text-[#475569] focus:outline-none"})]})}),e.jsx(ce,{stats:[{label:"Feature modules",icon:$n,value:String(m.length),note:"Suites A–G, Practice and Global Support"},t.entitlement?{label:"In entitlement",icon:Rt,value:String(p),delta:`of ${((u=t.profile)==null?void 0:u.modules.filter(g=>g.includes("/")).length)??0}`,deltaTone:"muted",note:`${(v=t.profile)==null?void 0:v.profile} · ${t.planTitle} plan`}:{label:"In entitlement",icon:Rt,value:"–",note:"Decided per organisation"},{label:"Backend built",icon:Ct,value:String(h.length),note:h.map(g=>g.id).join(", ")},{label:"Platform & integrations",icon:ur,value:String(Ce.length+Te.length),note:`${Ce.length} services · ${Te.length} adapters`}]}),e.jsxs("div",{className:"grid grid-cols-1 xl:grid-cols-12 gap-6 items-start",children:[e.jsxs("div",{className:"xl:col-span-8 space-y-5",children:[o.map(g=>e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden",children:[e.jsxs("header",{className:"px-4 py-3 bg-[#F6F8FB] border-b border-[#E2E8F0] flex items-center justify-between gap-2",children:[e.jsx("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F]",children:g.title}),e.jsx("code",{className:"text-[10px] text-[#64748B]",children:g.path})]}),e.jsx("ul",{className:"divide-y divide-[#F1F5F9]",children:g.modules.map(l=>{const x=Re(l,t);return e.jsxs("li",{className:"px-4 py-3 flex items-center gap-3 hover:bg-[#F6F8FB]",children:[e.jsx("span",{className:"w-1.5 h-8 rounded-full flex-shrink-0",style:{background:as(l)}}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsxs("div",{className:"flex items-center gap-2 flex-wrap",children:[e.jsx(W,{to:`/modules/${l.id}`,className:"text-xs font-semibold text-[#12233F] hover:text-[#7E22CE]",children:l.name}),e.jsx("span",{className:`text-[10px] px-1.5 py-0.5 rounded font-medium ${Fn[l.status]}`,children:l.status}),l.implemented&&e.jsx("span",{className:`text-[10px] px-1.5 py-0.5 rounded font-medium ${Fn.stable}`,children:"backend built"})]}),e.jsx("p",{className:"text-[11px] text-[#475569] truncate",children:l.description})]}),e.jsx("span",{className:`text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap ${Vs[x]}`,children:mt[x]})]},l.id)})})]},g.key)),o.length===0&&e.jsx("p",{className:"text-center text-xs text-[#475569] py-8",children:"No modules match."})]}),e.jsxs("aside",{className:"xl:col-span-4 xl:sticky xl:top-20 bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4",children:[e.jsxs("h3",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] mb-2 flex items-center gap-1.5",children:[e.jsx(ot,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),"Entitlement"]}),e.jsx("pre",{className:"text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto",children:Fc(t)}),e.jsxs("p",{className:"text-[11px] text-[#64748B] mt-2",children:["Computed by platform/tenancy from platform/identity/config/profiles and platform/billing/config/plans.yaml, and enforced per request by the entitlement gate in apps/backend. ",t.source==="preview"&&"Preview: the reference profile on the trial plan."]})]})]})]})},_c=Object.assign({"../../../../../modules/academics/academic-management/frontend/src/widgets/index.ts":Js,"../../../../../modules/academics/examinations/frontend/src/widgets/index.ts":Xs,"../../../../../modules/academics/lms/frontend/src/widgets/index.ts":Zs,"../../../../../modules/academics/timetable-attendance/frontend/src/widgets/index.ts":ea,"../../../../../modules/campus-life/alumni/frontend/src/widgets/index.ts":ta,"../../../../../modules/campus-life/hostel/frontend/src/widgets/index.ts":na,"../../../../../modules/campus-life/library/frontend/src/widgets/index.ts":sa,"../../../../../modules/campus-life/placement-career/frontend/src/widgets/index.ts":aa,"../../../../../modules/campus-life/transport/frontend/src/widgets/index.ts":ia,"../../../../../modules/facilities/asset-management/frontend/src/widgets/index.ts":ra,"../../../../../modules/facilities/facility-booking/frontend/src/widgets/index.ts":oa,"../../../../../modules/facilities/inventory-equipment/frontend/src/widgets/index.ts":la,"../../../../../modules/facilities/maintenance/frontend/src/widgets/index.ts":da,"../../../../../modules/facilities/sports-facilities/frontend/src/widgets/index.ts":ca,"../../../../../modules/finance-operations/budget-grants/frontend/src/widgets/index.ts":ma,"../../../../../modules/finance-operations/e-office/frontend/src/widgets/index.ts":pa,"../../../../../modules/finance-operations/fees-accounts/frontend/src/widgets/index.ts":ua,"../../../../../modules/finance-operations/hr-payroll/frontend/src/widgets/index.ts":ha,"../../../../../modules/finance-operations/procurement/frontend/src/widgets/index.ts":ga,"../../../../../modules/governance/grievance/frontend/src/widgets/index.ts":fa,"../../../../../modules/governance/iqac-accreditation/frontend/src/widgets/index.ts":ya,"../../../../../modules/governance/regulatory-reports/frontend/src/widgets/index.ts":xa,"../../../../../modules/governance/rti/frontend/src/widgets/index.ts":ba,"../../../../../modules/practice/field-training/frontend/src/widgets/index.ts":va,"../../../../../modules/practice/portfolio/frontend/src/widgets/index.ts":wa,"../../../../../modules/practice/productions/frontend/src/widgets/index.ts":ka,"../../../../../modules/practice/projects/frontend/src/widgets/index.ts":ja,"../../../../../modules/practice/selection-process/frontend/src/widgets/index.ts":Fa,"../../../../../modules/practice/skill-progress/frontend/src/widgets/index.ts":Na,"../../../../../modules/sports/athlete-performance/frontend/src/widgets/index.ts":_a,"../../../../../modules/sports/sports-nutrition-health/frontend/src/widgets/index.ts":Sa,"../../../../../modules/sports/tournament-events/frontend/src/widgets/index.ts":Aa,"../../../../../modules/sports/training-video-analysis/frontend/src/widgets/index.ts":Ea,"../../../../../modules/student-lifecycle/admissions/frontend/src/widgets/index.ts":Ca,"../../../../../modules/student-lifecycle/enrolment-registration/frontend/src/widgets/index.ts":Ma,"../../../../../modules/student-lifecycle/student-information/frontend/src/widgets/index.ts":Ra,"../../../../../modules/student-lifecycle/web-portal-cms/frontend/src/widgets/index.ts":Pa,"../../../../../modules/support/amc-vendor-support/frontend/src/widgets/index.ts":Da,"../../../../../modules/support/helpdesk/frontend/src/widgets/index.ts":Oa,"../../../../../modules/support/incident-management/frontend/src/widgets/index.ts":Ba,"../../../../../modules/support/knowledge-base/frontend/src/widgets/index.ts":La,"../../../../../modules/support/sla-management/frontend/src/widgets/index.ts":Ta}),ft=Object.fromEntries(Object.entries(_c).map(([t,n])=>[t.split("/").slice(-5,-4)[0],n.widgets??[]])),Nn={"student-information":{src:O("/students.jpg"),position:"50% 72%"},"enrolment-registration":{src:O("/enrolment.jpg"),position:"40% 60%"},"web-portal-cms":{src:O("/web-portal.jpg"),position:"60% 55%"},"academic-management":{src:O("/academics.jpg"),position:"70% 45%"},lms:{src:O("/lms.jpg"),position:"55% 45%"},"timetable-attendance":{src:O("/timetable.jpg"),position:"50% 40%"},examinations:{src:O("/examinations.jpg"),position:"50% 12%"},"athlete-performance":{src:O("/athletes.jpg"),position:"50% 42%"},"training-video-analysis":{src:O("/training.jpg"),position:"50% 30%"},"sports-nutrition-health":{src:O("/nutrition.jpg"),position:"50% 18%"},"tournament-events":{src:O("/tournaments.jpg"),position:"50% 30%"},"sports-facilities":{src:O("/facilities.jpg"),position:"50% 45%"},"facility-booking":{src:O("/facility-booking.jpg"),position:"50% 40%"},"inventory-equipment":{src:O("/inventory.jpg"),position:"50% 30%"},"asset-management":{src:O("/assets.jpg"),position:"50% 28%"},maintenance:{src:O("/maintenance.jpg"),position:"50% 30%"},"fees-accounts":{src:O("/fees.jpg"),position:"50% 55%"},"budget-grants":{src:O("/budget.jpg"),position:"50% 55%"},procurement:{src:O("/procurement.jpg"),position:"50% 50%"},"hr-payroll":{src:O("/hr-payroll.jpg"),position:"0% 50%"},hostel:{src:O("/hostel.jpg"),position:"50% 25%"},"e-office":{src:O("/e-office.jpg"),position:"50% 25%"},transport:{src:O("/transport.jpg"),position:"50% 25%"},portfolio:{src:O("/portfolio-v3.jpg"),position:"100% 50%"},projects:{src:O("/projects-v2.jpg"),position:"100% 50%"},"selection-process":{src:O("/selection-process.jpg"),position:"100% 50%"},productions:{src:O("/productions.jpg"),position:"100% 50%"},"field-training":{src:O("/field-training.jpg"),position:"100% 50%"},"skill-progress":{src:O("/skill-progress.jpg"),position:"100% 50%"},library:{src:O("/library.jpg"),position:"100% 50%"},alumni:{src:O("/alumni.jpg"),position:"100% 50%"},"placement-career":{src:O("/placement-career.jpg"),position:"100% 50%"},grievance:{src:O("/grievance.jpg"),position:"100% 50%"},rti:{src:O("/rti.jpg"),position:"100% 50%"},"iqac-accreditation":{src:O("/iqac-accreditation.jpg"),position:"100% 50%"}},Sc=(t,n,s)=>t==="feature"?`modules/${n}/${s}`:t==="platform"?`platform/${s}`:`integrations/${s}`,Ac=()=>{const{moduleId:t=""}=qa(),n=ye(),[s,a]=f.useState(null),i=Ge(t),o=y=>{a(y),setTimeout(()=>a(null),3e3)};if(!i)return e.jsxs("div",{className:"max-w-xl mx-auto py-16 text-center space-y-4",children:[e.jsxs("h1",{className:"text-xl font-bold text-[#12233F]",children:['Unknown module "',t,'"']}),e.jsx(W,{to:"/modules",className:"text-xs text-[var(--accent)] hover:underline",children:"Back to the module registry"})]});const m=wt(i.suiteId),p=Sc(i.kind,m==null?void 0:m.domain,i.id),h=Re(i,n),u=ss[i.id],v=Ad(i.id),g=new Set((ft[i.id]??[]).map(y=>y.id)),l=Sd(i.id),x=(Xe[i.id]??[]).map(y=>y.key),w=y=>Object.entries(je).filter(([,k])=>k.has(y)).map(([k])=>k),N=Is[i.id]??vc(i),b=[rs[i.id]??Un,Et,Ke,Qn],S=$s(i.id,N.chart.base,N.chart.split??0),E=N.chart.series.map((y,k)=>({key:k===0?"a":"b",name:y}));return e.jsxs(Bs,{theme:Jd(i.id),className:"space-y-8",children:[s&&e.jsxs("div",{className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs",children:[e.jsx(z,{className:"w-4 h-4 text-[#4ADE80]"}),e.jsx("span",{children:s})]}),e.jsx(me,{art:Nn[i.id]?e.jsx(Gt,{...Nn[i.id],fit:"right"}):void 0,eyebrow:e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-white"}),m?vt(m):i.kind==="platform"?"Shared platform service":"External integration"]}),title:i.name,subtitle:e.jsxs(e.Fragment,{children:[i.description,e.jsxs("span",{className:"block text-xs text-[#64748B] mt-0.5",children:[i.implemented?"Backend built · figures below are sample data":"Not built yet: sample data"," · ",mt[h]]})]}),actions:e.jsxs(e.Fragment,{children:[e.jsxs("button",{onClick:()=>o(`${N.action} needs the ${i.name} ${i.implemented?"screens":"module"}, which ${i.implemented?"are":"is"} not built yet`),className:Fe,children:[e.jsx(Yn,{className:"w-3.5 h-3.5"}),N.action]}),i.route?e.jsxs(W,{to:i.route,className:se,children:["Open workflow ",e.jsx(ge,{className:"w-3.5 h-3.5"})]}):e.jsxs("button",{onClick:()=>o(`Export needs the ${i.name} ${i.implemented?"screens":"module"}, which ${i.implemented?"are":"is"} not built yet`),className:se,children:[e.jsx(Tt,{className:"w-3.5 h-3.5 text-[#475569]"}),"Export"]}),e.jsxs("span",{className:se,title:"Decided by the organisation's academy profile and plan",children:[e.jsx(Rt,{className:"w-3.5 h-3.5 text-[#475569]"}),mt[h]]})]})}),e.jsx(ce,{stats:N.kpis.map((y,k)=>({label:y.label,icon:b[k],value:y.value,delta:y.delta,deltaTone:y.tone??"up",note:y.note}))}),e.jsx(zt,{title:N.chart.title,subtitle:N.chart.subtitle,data:S,xKey:"month",series:N.chart.split?E:E.slice(0,1),tooltipLabel:y=>`${y} 2026`}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsx(Kt,{title:N.breakdown.title,subtitle:N.breakdown.subtitle,items:N.breakdown.items.map(([y,k])=>({label:y,count:k})),relativeToFirst:!!N.breakdown.footer,unit:N.breakdown.unit,footer:N.breakdown.footer&&{label:N.breakdown.footer[0],value:N.breakdown.footer[1]}}),e.jsx("div",{className:"lg:col-span-2",children:e.jsx(ec,{items:N.actions.map((y,k)=>({id:`${i.id}-a${k}`,...y})),onOpen:y=>o(`${y.ref} is a sample item: the ${i.name} module is not built yet`)})})]}),e.jsx(Ts,{subtitle:`${i.name} audit trail`,items:N.activity.map((y,k)=>({id:`${i.id}-l${k}`,time:y.time,title:y.title,meta:e.jsxs(e.Fragment,{children:[y.who," · ",e.jsx("span",{className:"font-mono",children:y.ref})]}),status:y.status??"Success"}))}),e.jsxs("details",{className:`${H} group`,children:[e.jsxs("summary",{className:"list-none cursor-pointer px-5 py-4 flex items-center justify-between gap-4",children:[e.jsxs("div",{children:[e.jsx("h2",{className:"text-[13px] font-semibold text-[#12233F]",children:"Module details"}),e.jsxs("p",{className:"text-xs text-[#64748B] mt-0.5",children:["Manifest, permission keys and role dashboards · status ",i.status," · ",x.length," keys · ",v.length," widgets (",g.size," built) · on ",l.length," role dashboards"]})]}),e.jsx(ze,{className:"w-4 h-4 text-[#64748B] transition-transform group-open:rotate-180"})]}),e.jsx("div",{className:"px-5 pb-5 pt-1",children:e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-2 gap-6",children:[e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-2",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5",children:[e.jsx(ot,{className:"w-3.5 h-3.5 text-[var(--accent)]"})," ",p,"/module.yaml"]}),e.jsx("pre",{className:"text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto",children:`name: ${(u==null?void 0:u.name)??i.id}
  kind: ${(u==null?void 0:u.kind)??i.kind}
  domain: ${(u==null?void 0:u.domain)??(m==null?void 0:m.domain)??i.kind}
  tier: ${(u==null?void 0:u.tier)??""}${u!=null&&u.field?`
  field: ${u.field}`:""}
  status: ${(u==null?void 0:u.status)??i.status}
  description: "${i.description}"
  exposes:
    api: contracts/openapi.yaml        # /api/v1/${i.id}
    events: contracts/events.yaml      # ${i.id}.<entity>.<past-verb>
    permissions: contracts/permissions.yaml`}),e.jsx("p",{className:"text-[11px] text-[#64748B]",children:"Other modules reach this one only through these contracts and events, never by importing its code."})]}),e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] p-4 pb-2 flex items-center gap-1.5",children:[e.jsx(Ne,{className:"w-3.5 h-3.5 text-[var(--accent)]"})," Permission keys"]}),e.jsx("table",{className:"w-full text-xs",children:e.jsxs("tbody",{className:"divide-y divide-[#F1F5F9]",children:[x.length===0&&e.jsx("tr",{children:e.jsxs("td",{className:"py-2 px-4 text-[11px] text-[#475569]",children:["None defined yet in ",e.jsxs("span",{className:"font-mono",children:[p,"/contracts/permissions.yaml"]}),"."]})}),x.map(y=>{const k=w(y);return e.jsxs("tr",{children:[e.jsx("td",{className:"py-2 px-4 font-mono text-[11px] text-[#12233F] whitespace-nowrap",children:y}),e.jsx("td",{className:"py-2 px-4 text-[11px] text-[#475569]",children:k.length?k.map(J).join(", "):e.jsx("span",{className:"text-[#64748B]",children:"Not granted to any role yet"})})]},y)})]})}),e.jsx("div",{className:"p-3 border-t border-[#E2E8F0] text-right",children:e.jsx(W,{to:"/roles",className:"text-[11px] text-[var(--accent)] hover:underline",children:"See Roles & Permissions →"})})]}),e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-3",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5",children:[e.jsx(Me,{className:"w-3.5 h-3.5 text-[var(--accent)]"})," Dashboard widgets"]}),v.length?e.jsx("ul",{className:"space-y-1.5",children:v.map(y=>e.jsxs("li",{className:"flex items-center justify-between gap-2 text-[11px]",children:[e.jsx("code",{className:"text-[#334155]",children:y}),e.jsx("span",{className:g.has(y)?"text-[#126B3D]":"text-[#64748B]",children:g.has(y)?"built":"not built yet"})]},y))}):e.jsx("p",{className:"text-[11px] text-[#475569]",children:"No role layout references a widget from this module."}),e.jsxs("p",{className:"text-[11px] text-[#64748B]",children:["Exported from ",p,"/frontend/src/widgets/index.ts"]})]}),e.jsxs("section",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-3",children:[e.jsxs("h2",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5",children:[e.jsx(Je,{className:"w-3.5 h-3.5 text-[var(--accent)]"})," On these role dashboards"]}),l.length?e.jsx("div",{className:"flex flex-wrap gap-1.5",children:l.map(y=>e.jsx(W,{to:`/dashboards?role=${y}`,className:"text-[11px] px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155] hover:border-[#9333EA] hover:text-[#12233F]",children:J(y)},y))}):e.jsx("p",{className:"text-[11px] text-[#475569]",children:"None yet."})]})]})})]})]})},Ec={"1x1":"sm:col-span-1","2x1":"sm:col-span-2","2x2":"sm:col-span-2 sm:row-span-2",full:"sm:col-span-2"},Cc=()=>{const[t,n]=On(),s=ye(),{ROLES:a,ROLE_LAYOUTS:i,ROLES_PROFILE_TITLE:o}=Ut(),m=Object.keys(i),p=t.get("role")&&i[t.get("role")]?t.get("role"):"management",h=a.find(x=>x.id===p),u=i[p],v=f.useMemo(()=>{const x=new Set(h.permissions);return Pe(p).map(w=>{var y;const N=Ie(w),b=(y=ft[N])==null?void 0:y.find(k=>k.id===w);if(!b)return{id:w,state:{kind:"not-built"}};const S=Ge(N),E=S?Re(S,s):"not-in-profile";return E==="upgrade"?{id:w,state:{kind:"disabled",reason:"Not in this organisation's plan"}}:E==="not-in-profile"?{id:w,state:{kind:"disabled",reason:"Not in this academy profile"}}:x.has(b.permission)?{id:w,state:{kind:"ready",widget:b}}:{id:w,state:{kind:"hidden",permission:b.permission}}})},[p,h,s]),g=v.filter(x=>x.state.kind==="ready").length,l=m.map(x=>{const w=Pe(x),N=w.filter(b=>{var S;return(S=ft[Ie(b)])==null?void 0:S.some(E=>E.id===b)}).length;return{id:x,total:w.length,done:N}});return e.jsxs("div",{className:"space-y-6",children:[e.jsx(me,{title:"Role Dashboards",subtitle:e.jsxs(e.Fragment,{children:["One dashboard page, ",m.length," layouts (",o," profile and platform roles). Each role's widgets are listed in"," ",e.jsx("code",{className:"text-[#6B21A8]",children:"platform/identity/config/dashboards/<role>.yaml"}),"."]}),actions:e.jsxs("label",{className:"text-xs text-[#334155] flex items-center gap-2",children:["View as",e.jsx("select",{value:p,onChange:x=>n({role:x.target.value}),className:"h-8 px-3 rounded-md bg-[#FFFFFF] border border-[#E2E8F0] text-xs text-[#12233F] focus:outline-none focus:border-[#CBD5E1]",children:m.map(x=>e.jsx("option",{value:x,children:i[x].title},x))})]})}),e.jsx(ce,{stats:[{label:"Widgets on this dashboard",icon:Me,value:String(v.length),note:u.title},{label:"Live",icon:z,value:String(g),note:"Built and permitted"},{label:"Not built yet",icon:Ct,value:String(v.filter(x=>x.state.kind==="not-built").length),deltaTone:"alert",note:"No module exports these widgets yet"},{label:"Coverage, all roles",icon:ot,value:`${Math.round(l.reduce((x,w)=>x+w.done,0)/Math.max(1,l.reduce((x,w)=>x+w.total,0))*100)}%`,note:`Widgets built across ${m.length} layouts`}]}),e.jsxs("div",{className:"grid grid-cols-1 xl:grid-cols-12 gap-6 items-start",children:[e.jsxs("section",{className:"xl:col-span-8 space-y-3","aria-label":`${u.title} dashboard`,children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsx("h2",{className:"text-sm font-bold text-[#12233F]",children:u.title}),e.jsxs("span",{className:"text-[11px] text-[#475569]",children:[g," of ",v.length," widgets live"]})]}),e.jsx("div",{className:"grid grid-cols-1 sm:grid-cols-4 gap-3 auto-rows-[minmax(130px,auto)]",children:v.map(({id:x,state:w})=>{const N=Ge(Ie(x)),b=w.kind==="ready"?w.widget.size:"1x1",S=N?as(N):"#64748B";return e.jsxs("article",{className:`rounded-xl border p-4 flex flex-col gap-2 ${Ec[b]} ${w.kind==="ready"?"bg-[#FFFFFF] border-[#E2E8F0]":"bg-[#FFFFFF] border-dashed border-[#CBD5E1]"}`,children:[e.jsxs("header",{className:"flex items-start justify-between gap-2",children:[e.jsx("h3",{className:"text-xs font-semibold text-[#12233F] leading-snug",children:w.kind==="ready"?w.widget.title:x}),e.jsx("span",{className:"w-2 h-2 rounded-full mt-1 flex-shrink-0",style:{background:S}})]}),e.jsxs("div",{className:"flex-1",children:[w.kind==="ready"&&e.jsx(w.widget.component,{role:p}),w.kind==="not-built"&&e.jsxs("p",{className:"text-[11px] text-[#475569] flex items-center gap-1.5",children:[e.jsx(Ct,{className:"w-3.5 h-3.5"})," Not built yet"]}),w.kind==="disabled"&&e.jsxs("p",{className:"text-[11px] text-[#8A4F00] flex items-center gap-1.5",children:[e.jsx(hr,{className:"w-3.5 h-3.5"})," ",w.reason]}),w.kind==="hidden"&&e.jsxs("p",{className:"text-[11px] text-[#B91C1C] flex items-center gap-1.5",children:[e.jsx(Xi,{className:"w-3.5 h-3.5"})," Hidden: role lacks ",e.jsx("code",{children:w.permission})]})]}),N&&e.jsxs(W,{to:`/modules/${N.id}`,className:"text-[10px] font-mono text-[#64748B] hover:text-[#7E22CE] truncate",children:[N.id,w.kind==="ready"||w.kind==="hidden"?` · needs ${w.kind==="ready"?w.widget.permission:w.permission}`:""]})]},x)})})]}),e.jsxs("aside",{className:"xl:col-span-4 space-y-4",children:[e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4",children:[e.jsxs("h3",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] mb-2 flex items-center gap-1.5",children:[e.jsx(ot,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),u.role,".yaml"]}),e.jsx("pre",{className:"text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto",children:`role: ${u.role}
title: "${u.title}"${u.extends?`
extends: ${u.extends}`:""}
widgets:
${u.widgets.map(x=>`  - ${x}`).join(`
`)}`})]}),e.jsxs("div",{className:"bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden",children:[e.jsx("h3",{className:"text-[13px] font-bold uppercase tracking-wide text-[#12233F] p-4 pb-2",children:"Widget coverage by role"}),e.jsx("table",{className:"w-full text-xs",children:e.jsx("tbody",{className:"divide-y divide-[#F1F5F9]",children:l.map(x=>e.jsxs("tr",{onClick:()=>n({role:x.id}),className:`cursor-pointer hover:bg-[#F6F8FB] ${x.id===p?"bg-[#7E22CE26]":""}`,children:[e.jsx("td",{className:"py-2 px-4 text-[#12233F]",children:i[x.id].title}),e.jsxs("td",{className:"py-2 px-4 text-right text-[#475569] whitespace-nowrap",children:[x.done," / ",x.total]})]},x.id))})})]})]})]})]})},ve="w-full px-3 py-2 text-xs rounded-lg border border-[#E2E8F0] text-[#12233F] placeholder-[#64748B] focus:outline-none focus:ring-2 focus:ring-[#9333EA] focus:border-transparent bg-[#F6F8FB]",$=({label:t,children:n,muted:s})=>e.jsxs("div",{className:"px-5 py-3 flex items-start justify-between gap-4 text-xs",children:[e.jsx("span",{className:"text-[#64748B] flex-shrink-0",children:t}),e.jsx("span",{className:`text-right min-w-0 ${s?"text-[#64748B]":"text-[#12233F] font-semibold"}`,style:{overflowWrap:"anywhere"},children:n})]}),Le=({children:t="Not available yet"})=>e.jsx("span",{className:"inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#475569] whitespace-nowrap",children:t}),we=({label:t,error:n,hint:s,children:a})=>e.jsxs("label",{className:"block",children:[e.jsx("span",{className:"block text-xs font-semibold text-[#12233F] mb-1.5",children:t}),a,n?e.jsx("span",{role:"alert",className:"block mt-1 text-[11px] text-[#B91C1C]",children:n}):s&&e.jsx("span",{className:"block mt-1 text-[11px] text-[#64748B]",children:s})]});function Mc(t){const n={};return t.firstName.trim()||(n.firstName="First name is required."),t.lastName.trim()||(n.lastName="Last name is required."),t.displayName.trim().length>60&&(n.displayName="Keep the display name under 60 characters."),t.phone&&!/^\+?[0-9 ()-]{7,20}$/.test(t.phone.trim())&&(n.phone="Enter a valid phone number, e.g. +91 98765 43210."),t.jobTitle.trim().length>80&&(n.jobTitle="Keep the job title under 80 characters."),t.bio.length>300&&(n.bio=`${t.bio.length}/300 characters: please shorten.`),n}const Rc=()=>{const{session:t,preview:n,signOut:s}=ie(),a=xt(),i=ye(),o=!t,m=(t==null?void 0:t.me)??{id:"preview",email:"admin@example.org",name:"Administrator",roles:["org-admin"],is_super_admin:!1,permissions:$t(["org-admin"])},p=(t==null?void 0:t.organisation)??null,h=(p==null?void 0:p.country)??null,u=m.is_super_admin?"super-admin":m.roles[0]??"org-admin",v=i.profile?dt(i.profile):"–",g=(p==null?void 0:p.name)??(o?"Demo organisation":m.is_super_admin?"Education OS platform":"–"),[l,x]=us(m.id),[w,...N]=m.name.split(/\s+/).filter(Boolean),b={firstName:l.firstName||w||"",lastName:l.lastName||N.join(" "),displayName:l.displayName,phone:l.phone,jobTitle:l.jobTitle,bio:l.bio},S=b.displayName||[b.firstName,b.lastName].filter(Boolean).join(" ")||m.name||m.email,[E,y]=f.useState(!1),[k,B]=f.useState(b),[T,C]=f.useState({}),[M,j]=f.useState(null),P=f.useRef(null),[R,_]=f.useState(null),[D,I]=f.useState(!1),[pe,Z]=f.useState(null),X=R??l.photo,V=(L,q)=>{j({ok:L,text:q}),window.setTimeout(()=>j(null),3500)},ee=(L,q)=>{try{return x({...l,...L}),V(!0,q),!0}catch{return V(!1,"Could not save: this browser is blocking storage (private window or storage full)."),!1}},te=()=>{B(b),C({}),y(!0)},re=L=>{L.preventDefault();const q=Mc(k);if(C(q),Object.keys(q).length)return;const A=Object.fromEntries(Object.entries(k).map(([ne,Q])=>[ne,Q.trim()]));ee(A,"Profile details saved on this device")&&y(!1)},_e=async L=>{if(L){Z(null),I(!0);try{_(await wd(L))}catch(q){Z(q instanceof Error?q.message:"This image could not be used.")}finally{I(!1),P.current&&(P.current.value="")}}},Se=()=>{R&&ee({photo:R},"Profile photo saved on this device")&&_(null)},Be=()=>{_(null),l.photo&&window.confirm("Remove your profile photo?")&&ee({photo:null},"Profile photo removed")},xe=Intl.DateTimeFormat().resolvedOptions().timeZone,Ae=typeof navigator<"u"?navigator.language:"en";return e.jsxs("div",{className:"space-y-6",children:[M&&e.jsxs("div",{role:"status",className:"fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs",children:[M.ok?e.jsx(z,{className:"w-4 h-4 text-[#6FCF97]"}):e.jsx(Ye,{className:"w-4 h-4",style:{color:"#F39A19"}}),e.jsx("span",{children:M.text})]}),e.jsx("header",{className:"eos-hero relative rounded-xl px-6 py-7 sm:px-8 text-white overflow-hidden",children:e.jsxs("div",{className:"relative z-10 flex flex-col md:flex-row md:items-center gap-5",children:[e.jsxs("div",{className:"relative flex-shrink-0 self-start",children:[e.jsx("div",{className:"rounded-full overflow-hidden flex items-center justify-center text-2xl font-bold shadow-lg",style:{width:96,height:96,background:X?"#FFFFFF":"#D03F1B",boxShadow:"0 0 0 4px rgba(255,255,255,0.35)"},children:X?e.jsx("img",{src:X,alt:"Profile photo",className:"w-full h-full",style:{objectFit:"cover"}}):kt(S)}),e.jsx("button",{type:"button",onClick:()=>{var L;return(L=P.current)==null?void 0:L.click()},"aria-label":"Change profile photo",title:"Change profile photo",className:"absolute bottom-0 right-0 w-8 h-8 rounded-full bg-white text-[#7E22CE] flex items-center justify-center shadow-lg",children:e.jsx(_r,{className:"w-4 h-4"})})]}),e.jsxs("div",{className:"min-w-0 flex-1",children:[e.jsxs("div",{className:"eos-hero-sub text-[12px] font-medium mb-1 inline-flex items-center gap-1.5",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-white"}),J(u)]}),e.jsx("h1",{className:"text-[32px] leading-tight font-bold tracking-[-0.02em] text-white truncate",children:S}),e.jsxs("p",{className:"eos-hero-sub text-[14px] mt-1 truncate",children:[b.jobTitle?`${b.jobTitle} · `:"",g]}),e.jsxs("div",{className:"mt-3 flex flex-wrap items-center gap-2",children:[e.jsxs("span",{className:"inline-flex items-center gap-1.5 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-white text-[#126B3D]",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-[#16834B]"}),o?"Preview":"Active"]}),e.jsx("span",{className:"text-[11px] font-semibold px-2 py-0.5 rounded-full",style:{background:"rgba(255,255,255,0.16)"},children:v})]})]}),e.jsx("div",{className:"flex flex-wrap gap-2.5",children:e.jsxs("button",{type:"button",onClick:te,className:Fe,children:[e.jsx(rn,{className:"w-3.5 h-3.5"}),"Edit Profile"]})})]})}),e.jsx("input",{ref:P,type:"file",accept:"image/jpeg,image/png,image/webp",className:"hidden","aria-label":"Profile photo file",onChange:L=>{var q;return _e((q=L.target.files)==null?void 0:q[0])}}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-3 gap-6",children:[e.jsxs("section",{className:`${H} eos-lift`,children:[e.jsx(G,{title:"Profile Photo",subtitle:`JPG, PNG or WebP · up to ${hs/1048576} MB`}),e.jsxs("div",{className:"px-5 pb-5 flex flex-col items-center gap-4",children:[e.jsx("div",{className:"rounded-full overflow-hidden flex items-center justify-center font-bold text-white",style:{fontSize:30,width:120,height:120,background:X?"#F6F8FB":"#D03F1B",boxShadow:R?"0 0 0 3px #9333EA":"0 0 0 1px #E2E8F0"},children:D?e.jsx("span",{className:"w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin","aria-label":"Processing image"}):X?e.jsx("img",{src:X,alt:R?"New photo preview":"Profile photo",className:"w-full h-full",style:{objectFit:"cover"}}):kt(S)}),R&&e.jsx("p",{className:"text-[11px] font-semibold text-[#7E22CE]",children:"Preview: not saved yet"}),pe&&e.jsx("p",{role:"alert",className:"w-full rounded-lg border border-[#FECACA] bg-[#FEF2F2] px-3 py-2 text-xs text-[#B91C1C]",children:pe}),e.jsx("div",{className:"flex flex-wrap justify-center gap-2",children:R?e.jsxs(e.Fragment,{children:[e.jsxs("button",{type:"button",onClick:Se,className:Fe,children:[e.jsx(an,{className:"w-3.5 h-3.5"}),"Save Photo"]}),e.jsxs("button",{type:"button",onClick:()=>_(null),className:se,children:[e.jsx(ae,{className:"w-3.5 h-3.5"}),"Cancel"]})]}):e.jsxs(e.Fragment,{children:[e.jsxs("button",{type:"button",onClick:()=>{var L;return(L=P.current)==null?void 0:L.click()},disabled:D,className:se,children:[e.jsx(Sr,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),l.photo?"Replace":"Upload"]}),l.photo&&e.jsxs("button",{type:"button",onClick:Be,className:se,children:[e.jsx(Ar,{className:"w-3.5 h-3.5 text-[#B91C1C]"}),"Remove"]})]})}),e.jsx("p",{className:"text-[11px] text-[#64748B] text-center",children:"Saved on this device. Photo storage needs platform/documents, which is not built yet."})]})]}),e.jsxs("section",{className:`${H} lg:col-span-2 eos-lift`,children:[e.jsx(G,{title:"Personal Information",subtitle:E?"Edit your details, then save":"Your details as people in your organisation see them",action:!E&&e.jsxs("button",{type:"button",onClick:te,className:"inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:opacity-80 pt-0.5",children:[e.jsx(rn,{className:"w-3.5 h-3.5"}),"Edit"]})}),E?e.jsxs("form",{onSubmit:re,noValidate:!0,className:"px-5 pb-5 space-y-4 page-enter",children:[e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 gap-4",children:[e.jsx(we,{label:"First Name *",error:T.firstName,children:e.jsx("input",{className:ve,value:k.firstName,onChange:L=>B({...k,firstName:L.target.value}),autoFocus:!0})}),e.jsx(we,{label:"Last Name *",error:T.lastName,children:e.jsx("input",{className:ve,value:k.lastName,onChange:L=>B({...k,lastName:L.target.value})})}),e.jsx(we,{label:"Display Name",error:T.displayName,hint:"Leave empty to use your full name.",children:e.jsx("input",{className:ve,value:k.displayName,onChange:L=>B({...k,displayName:L.target.value})})}),e.jsx(we,{label:"Email",hint:"Your sign-in email. Changing it is not in the identity API yet.",children:e.jsx("input",{className:ve,style:{opacity:.7,cursor:"not-allowed"},value:m.email,readOnly:!0,"aria-readonly":!0})}),e.jsx(we,{label:"Phone Number",error:T.phone,children:e.jsx("input",{className:ve,type:"tel",value:k.phone,onChange:L=>B({...k,phone:L.target.value}),placeholder:"+91 98765 43210"})}),e.jsx(we,{label:"Job Title / Designation",error:T.jobTitle,children:e.jsx("input",{className:ve,value:k.jobTitle,onChange:L=>B({...k,jobTitle:L.target.value}),placeholder:"e.g. Registrar"})})]}),e.jsx(we,{label:"Bio",error:T.bio,hint:`${k.bio.length}/300`,children:e.jsx("textarea",{className:ve,rows:3,value:k.bio,onChange:L=>B({...k,bio:L.target.value})})}),e.jsxs("div",{className:"flex flex-wrap items-center justify-between gap-3 pt-1",children:[e.jsx("p",{className:"text-[11px] text-[#64748B]",children:"Saved on this device until profile editing is added to platform/identity."}),e.jsxs("div",{className:"flex gap-2",children:[e.jsxs("button",{type:"button",onClick:()=>y(!1),className:se,children:[e.jsx(ae,{className:"w-3.5 h-3.5"}),"Cancel"]}),e.jsxs("button",{type:"submit",className:Fe,children:[e.jsx(an,{className:"w-3.5 h-3.5"}),"Save Changes"]})]})]})]}):e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 border-t border-[#F1F5F9]",children:[e.jsxs("div",{className:"divide-y divide-[#F1F5F9]",children:[e.jsx($,{label:"First Name",children:b.firstName||"–"}),e.jsx($,{label:"Last Name",children:b.lastName||"–"}),e.jsx($,{label:"Display Name",muted:!b.displayName,children:b.displayName||"Not set"}),e.jsx($,{label:"Email",children:m.email})]}),e.jsxs("div",{className:"divide-y divide-[#F1F5F9]",children:[e.jsx($,{label:"Phone Number",muted:!b.phone,children:b.phone||"Not set"}),e.jsx($,{label:"Job Title",muted:!b.jobTitle,children:b.jobTitle||"Not set"}),e.jsx($,{label:"Bio",muted:!b.bio,children:b.bio||"Not set"}),e.jsx($,{label:"Last updated",muted:!0,children:l.updatedAt?new Date(l.updatedAt).toLocaleString("en-IN"):"Never"})]})]})]})]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-2 gap-6",children:[e.jsxs("section",{className:`${H} eos-lift`,children:[e.jsx(G,{title:"Organisation Information",subtitle:"platform/tenancy · read-only"}),e.jsxs("div",{className:"px-5 pb-3 flex items-center gap-3",children:[e.jsx("span",{className:"rounded-xl flex items-center justify-center text-sm font-bold text-white flex-shrink-0",style:{width:44,height:44,background:"var(--hero-gradient)"},children:kt(g)}),e.jsxs("div",{className:"min-w-0",children:[e.jsx("p",{className:"text-[13px] font-semibold text-[#12233F] truncate",children:g}),e.jsx("p",{className:"text-[11px] text-[#64748B]",children:"Logo upload needs platform/documents (not built)"})]})]}),e.jsxs("div",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:[e.jsx($,{label:"Organisation Name",children:g}),e.jsx($,{label:"Organisation Type",children:v}),e.jsx($,{label:"Short Name",children:e.jsx("span",{className:"font-mono text-[11px] font-normal",children:(p==null?void 0:p.slug)??"–"})}),e.jsx($,{label:"Country",muted:!h,children:h??"Not recorded"}),e.jsx($,{label:"Organisation Email",muted:!0,children:"Not recorded"}),e.jsx($,{label:"Organisation Phone",muted:!0,children:"Not recorded"}),e.jsx($,{label:"Website",muted:!0,children:"Not recorded"}),e.jsx($,{label:"Address · City · State",muted:!0,children:"Not recorded"})]}),e.jsxs("p",{className:"px-5 py-3 text-[11px] text-[#64748B] border-t border-[#F1F5F9]",children:["Read-only: editing (",e.jsx("code",{children:"PATCH /tenancy/organisation"}),") is in the tenancy contract but not built yet, and the organisation record has no contact or address fields."]})]}),e.jsxs("div",{className:"space-y-6",children:[e.jsxs("section",{className:`${H} eos-lift`,children:[e.jsx(G,{title:"Role & Access",subtitle:"Assigned by your organisation; you cannot change your own role",action:e.jsx(W,{to:"/access",className:"text-xs font-medium text-[var(--accent)] hover:underline pt-0.5",children:"Details"})}),e.jsxs("div",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:[e.jsx($,{label:"Role",children:e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx(de,{className:"w-3.5 h-3.5 text-[#7E22CE]"}),J(u)]})}),e.jsx($,{label:"Scope",children:m.is_super_admin?"All organisations":`${g} only`}),e.jsx($,{label:"Permission keys",children:e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx(Ne,{className:"w-3.5 h-3.5 text-[#475569]"}),m.permissions.length]})})]})]}),e.jsxs("section",{className:`${H} eos-lift`,children:[e.jsx(G,{title:"Security",subtitle:"Sign-in is email and password (platform/identity)"}),e.jsxs("div",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:[e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs",children:[e.jsxs("span",{className:"inline-flex items-center gap-2 text-[#12233F] font-semibold",children:[e.jsx(Gn,{className:"w-3.5 h-3.5 text-[#475569]"}),"Change Password"]}),e.jsx(Le,{})]}),e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs",children:[e.jsxs("span",{className:"inline-flex items-center gap-2 text-[#12233F] font-semibold",children:[e.jsx(Cr,{className:"w-3.5 h-3.5 text-[#475569]"}),"Two-Factor Authentication"]}),e.jsx(Le,{})]}),e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs",children:[e.jsxs("span",{className:"inline-flex items-center gap-2 text-[#12233F] font-semibold",children:[e.jsx(Oe,{className:"w-3.5 h-3.5 text-[#475569]"}),"This device"]}),e.jsxs("button",{type:"button",onClick:()=>{s(),a("/login",{replace:!0})},className:"inline-flex items-center gap-1 text-xs font-semibold text-[#B91C1C] hover:opacity-80",children:[e.jsx(Wn,{className:"w-3.5 h-3.5"}),"Sign out"]})]}),e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs",children:[e.jsx("span",{className:"text-[#475569]",children:"Sign out other devices"}),e.jsx(Le,{})]})]})]})]})]}),e.jsxs("section",{className:`${H} eos-lift`,children:[e.jsx(G,{title:"Notifications & Preferences",subtitle:"Notification settings need platform/notification, which is not built yet"}),e.jsx("div",{className:"grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 border-t border-[#F1F5F9]",children:[{icon:Er,label:"Email notifications",value:e.jsx(Le,{})},{icon:In,label:"Important system notices",value:e.jsx(Le,{})},{icon:Mr,label:"Language",value:e.jsxs("span",{className:"text-[#12233F] font-semibold",children:[Ae," (browser)"]})},{icon:Ke,label:"Time zone",value:e.jsxs("span",{className:"text-[#12233F] font-semibold text-right",style:{overflowWrap:"anywhere"},children:[xe," (browser)"]})},{icon:Rr,label:"Theme",value:e.jsx("span",{className:"text-[#12233F] font-semibold",children:"Light"})}].map(({icon:L,label:q,value:A})=>e.jsxs("div",{className:"px-5 py-3 flex items-center justify-between gap-3 text-xs border-b border-[#F1F5F9]",children:[e.jsxs("span",{className:"inline-flex items-center gap-2 text-[#475569] flex-shrink-0",children:[e.jsx(L,{className:"w-3.5 h-3.5"}),q]}),A]},q))})]}),n&&e.jsx("p",{className:"text-[11px] text-[#64748B] text-center",children:"Preview mode: sample account, no API connected."})]})},Pc=`from __future__ import annotations

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
`,Dc=`from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, status
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
    user = service.create_user(
        db,
        organisation_id=p.organisation_id,
        email=body.email,
        name=body.name,
        password=body.password,
        roles=body.roles,
    )
    db.commit()
    return user.to_dict()
`,Oc=`from __future__ import annotations

from eos_core.db import get_db
from eos_core.settings import settings
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query
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


class Impersonate(BaseModel):
    user_id: str
    reason: str


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
`,Bc=Object.assign({"../../../../../platform/billing/backend/src/eos_billing/api/router.py":Pc,"../../../../../platform/identity/backend/src/eos_identity/api/router.py":Dc,"../../../../../platform/tenancy/backend/src/eos_tenancy/api/router.py":Oc}),Lc=t=>t.replace(/_/g," ").replace(/^\w/,n=>n.toUpperCase());function Tc(t,n){return n.split(/^(?=@router\.)/m).slice(1).flatMap(a=>{var v,g,l;const i=a.match(/^@router\.(get|post|put|patch|delete)\("([^"]+)"/);if(!i)return[];const o=((v=a.match(/def\s+(\w+)\s*\(/))==null?void 0:v[1])??"",m=(l=(g=a.match(/"""\s*([^\n"]+)/))==null?void 0:g[1])==null?void 0:l.trim(),p=a.match(/require\("([^"]+)"(,\s*organisation=True)?\s*\)/),h=p==null?void 0:p[1],u=h?p!=null&&p[2]?{kind:"permission",key:h,organisation:!0}:{kind:"permission",key:h}:/require_organisation/.test(a)?{kind:"organisation"}:/current_principal/.test(a)?{kind:"signed-in"}:{kind:"public"};return[{service:t,method:i[1].toUpperCase(),path:`/api/v1/${t}${i[2]}`,summary:m??Lc(o),requires:u}]})}const Ic=Object.entries(Bc).flatMap(([t,n])=>{var a;const s=((a=t.split("/platform/")[1])==null?void 0:a.split("/")[0])??"";return Tc(s,n)});function _n(t,n){switch(t.requires.kind){case"permission":{if(t.requires.organisation&&!n.organisationId)return!1;const s=n.organisationId?je.member??new Set:new Set;return n.permissions.includes(t.requires.key)||s.has(t.requires.key)}case"organisation":return!!n.organisationId;default:return!0}}const $c=t=>t.kind==="permission"?t.organisation?`${t.key} (organisation user)`:t.key:t.kind==="organisation"?"organisation user":t.kind==="signed-in"?"any signed-in user":"public",Vc=new Map(Object.values(Xe).flatMap(t=>t.map(n=>[n.key,n.description??""]))),qc={GET:"bg-[#EEEEFD] text-[#4338CA]",POST:"bg-[#E7F4EC] text-[#126B3D]",PUT:"bg-[#FEF3E2] text-[#8A4F00]",PATCH:"bg-[#FEF3E2] text-[#8A4F00]",DELETE:"bg-[#FEF2F2] text-[#B91C1C]"},Hc=()=>{var S,E;const{session:t}=ie(),n=ye(),s=!t,a=(t==null?void 0:t.me)??{name:"Administrator",email:"admin@example.org",roles:["org-admin"],is_super_admin:!1,permissions:$t(["org-admin"]),organisation_id:"preview"},i=a.is_super_admin?"super-admin":a.roles[0]??"org-admin",o={permissions:a.permissions,organisationId:a.organisation_id},m=a.is_super_admin?"Platform-wide: every organisation, plan and subscription. Outside every organisation.":`One organisation: ${((S=t==null?void 0:t.organisation)==null?void 0:S.name)??"the demo organisation"}${n.profile?` (${dt(n.profile)})`:""}.`,p=Ic.filter(y=>y.requires.kind!=="public"),h=p.filter(y=>_n(y,o)),u=[...new Set(p.map(y=>y.service))],v=[...new Set(Object.values(Xe).flatMap(y=>y.map(k=>k.key)))].filter(y=>y.startsWith("platform:")||y.startsWith("tenancy:")||y.startsWith("billing:")).sort(),g=new Set(a.permissions),l=["included","upgrade","not-in-profile"],x=fe.map(y=>({suite:y,counts:l.map(k=>y.modules.filter(B=>Re(B,n)===k).length)})),w=lt[i],N=w?Pe(i):[],b=new Set(Object.values(ft).flat().map(y=>y.id));return e.jsxs("div",{className:"space-y-6",children:[e.jsx(me,{eyebrow:e.jsxs("span",{className:"inline-flex items-center gap-1.5",children:[e.jsx("span",{className:"w-1.5 h-1.5 rounded-full bg-white"}),a.name||a.email]}),title:"Role & Access",subtitle:e.jsxs(e.Fragment,{children:[J(i)," · ",m,s&&e.jsx("span",{className:"block text-xs mt-0.5",children:"Preview: sample organisation admin, no API connected"})]})}),e.jsx(ce,{stats:[{label:"Role",icon:de,value:a.is_super_admin?"Super Admin":J(i),note:i},{label:"Scope",icon:Oe,value:a.is_super_admin?"Platform":"Organisation",note:a.is_super_admin?"All organisations":((E=t==null?void 0:t.organisation)==null?void 0:E.name)??"Demo"},{label:"Permission keys",icon:Ne,value:String(a.permissions.length),note:`of ${v.length} platform keys`},{label:"API actions allowed",icon:rt,value:String(h.length),delta:`of ${p.length}`,deltaTone:"muted",note:"identity, tenancy, billing"}]}),e.jsxs("div",{className:"grid grid-cols-1 lg:grid-cols-2 gap-6",children:[e.jsxs("section",{className:H,children:[e.jsx(G,{title:"Permission keys",subtitle:"Granted to your role in contracts/permissions.yaml"}),e.jsx("ul",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:v.map(y=>{const k=g.has(y);return e.jsxs("li",{className:"px-5 py-2.5 flex items-start gap-3 text-[11px]",children:[e.jsx("span",{className:`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 ${k?"bg-[#16834B26] text-[#126B3D]":"bg-[#F1F5F9] text-[#64748B]"}`,"aria-label":k?"granted":"not granted",children:k?e.jsx(Ve,{className:"w-3.5 h-3.5"}):e.jsx(ae,{className:"w-3.5 h-3.5"})}),e.jsxs("div",{className:"min-w-0",children:[e.jsx("code",{className:k?"text-[#12233F]":"text-[#64748B]",children:y}),e.jsx("p",{className:"text-[#64748B]",children:Vc.get(y)})]})]},y)})})]}),e.jsxs("section",{className:H,children:[e.jsx(G,{title:"Module access",subtitle:n.entitlement?`${n.profile?dt(n.profile):""} · ${n.planTitle} plan`:"Decided per organisation by profile and plan",action:e.jsx(W,{to:"/modules",className:"text-xs font-medium text-[var(--accent)] hover:underline pt-0.5",children:"Module Registry"})}),n.entitlement?e.jsxs("table",{className:"w-full text-xs border-t border-[#F1F5F9]",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"text-[#475569]",children:[e.jsx("th",{className:"py-2 px-5 text-left font-semibold",children:"Suite"}),l.map(y=>e.jsx("th",{className:"py-2 px-2 text-center font-semibold",children:e.jsx("span",{className:`inline-flex text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap ${Vs[y]}`,children:mt[y]})},y))]})}),e.jsx("tbody",{className:"divide-y divide-[#F1F5F9]",children:x.map(({suite:y,counts:k})=>e.jsxs("tr",{children:[e.jsx("td",{className:"py-2 px-5 text-[#12233F]",children:vt(y)}),k.map((B,T)=>e.jsx("td",{className:`py-2 px-2 text-center tabular-nums ${B?"text-[#12233F] font-semibold":"text-[#94A3B8]"}`,children:B},T))]},y.id))})]}):e.jsxs("p",{className:"px-5 py-4 text-xs text-[#475569] border-t border-[#F1F5F9]",children:["A super admin is outside every organisation. Each organisation's modules are its academy profile ∩ plan, plus any overrides you grant with ",e.jsx("code",{children:"platform:entitlements:manage"}),"."]})]})]}),e.jsxs("section",{className:H,children:[e.jsx(G,{title:"API actions",subtitle:"Every platform endpoint and whether your role may call it, read from the backend routers"}),e.jsx("div",{className:"divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]",children:u.map(y=>e.jsxs("div",{className:"px-5 py-3 space-y-1.5",children:[e.jsx("div",{className:"text-[11px] font-bold uppercase tracking-wider text-[#475569]",children:y}),p.filter(k=>k.service===y).map(k=>{const B=_n(k,o);return e.jsxs("div",{className:"flex items-center gap-3 text-[11px]",children:[e.jsx("span",{className:`w-12 text-center text-[10px] font-semibold px-1.5 py-0.5 rounded ${qc[k.method]??""}`,children:k.method}),e.jsx("code",{className:`truncate ${B?"text-[#12233F]":"text-[#94A3B8]"}`,children:k.path}),e.jsx("span",{className:"hidden md:block flex-1 truncate text-[#64748B]",children:k.summary}),e.jsx("code",{className:"hidden sm:block text-[10px] text-[#64748B] whitespace-nowrap",children:$c(k.requires)}),e.jsx("span",{className:`text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${B?"bg-[#16834B26] text-[#126B3D]":"bg-[#F1F5F9] text-[#64748B]"}`,children:B?"Allowed":"Not allowed"})]},k.method+k.path)})]},y))})]}),e.jsxs("section",{className:H,children:[e.jsx(G,{title:"Your dashboard layout",subtitle:w?`platform/identity/config/dashboards/${i}.yaml`:"No layout for this role",action:w&&e.jsx(W,{to:`/dashboards?role=${i}`,className:"text-xs font-medium text-[var(--accent)] hover:underline pt-0.5",children:"Preview"})}),e.jsx("div",{className:"px-5 pb-4 flex flex-wrap gap-1.5",children:N.map(y=>e.jsxs("span",{className:"inline-flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155]",children:[e.jsx(Me,{className:"w-3 h-3 text-[#64748B]"}),y,e.jsx("span",{className:b.has(y)?"text-[#126B3D]":"text-[#94A3B8]",children:b.has(y)?"built":"widget not built yet"})]},y))})]})]})},Sn=({signedIn:t,to:n})=>{const{status:s}=ie();return s==="loading"?null:s==="signed-in"===t?e.jsx(Bn,{}):e.jsx(St,{to:n,replace:!0})},Uc=()=>e.jsx(za,{children:e.jsx(Va,{children:e.jsxs(Ga,{children:[e.jsx(U,{element:e.jsx(Sn,{signedIn:!1,to:"/dashboard"}),children:e.jsx(U,{path:"/login",element:e.jsx(nd,{})})}),e.jsx(U,{element:e.jsx(Sn,{signedIn:!0,to:"/login"}),children:e.jsxs(U,{element:e.jsx(Fd,{}),children:[e.jsx(U,{path:"/dashboard",element:e.jsx(hc,{})}),e.jsx(U,{path:"/admissions",element:e.jsx(kc,{})}),e.jsx(U,{path:"/users",element:e.jsx(fc,{})}),e.jsx(U,{path:"/roles",element:e.jsx(bc,{})}),e.jsx(U,{path:"/dashboards",element:e.jsx(Cc,{})}),e.jsx(U,{path:"/modules",element:e.jsx(Nc,{})}),e.jsx(U,{path:"/modules/:moduleId",element:e.jsx(Ac,{})}),e.jsx(U,{path:"/audit-logs",element:e.jsx(jc,{})}),e.jsx(U,{path:"/profile",element:e.jsx(Rc,{})}),e.jsx(U,{path:"/access",element:e.jsx(Hc,{})}),e.jsx(U,{path:"/",element:e.jsx(St,{to:"/dashboard",replace:!0})}),e.jsx(U,{path:"*",element:e.jsx(St,{to:"/dashboard",replace:!0})})]})})]})})});document.addEventListener("pointerdown",t=>{const n=t.target.closest("button");if(!n||n.disabled)return;const s=n.getBoundingClientRect(),a=Math.max(s.width,s.height);getComputedStyle(n).position==="static"&&(n.style.position="relative"),n.style.overflow="hidden";const i=document.createElement("span");i.className="ripple",i.style.width=i.style.height=`${a}px`,i.style.left=`${t.clientX-s.left-a/2}px`,i.style.top=`${t.clientY-s.top-a/2}px`,n.appendChild(i),i.addEventListener("animationend",()=>i.remove())});Qs.createRoot(document.getElementById("root")).render(e.jsx(Cn.StrictMode,{children:e.jsx(Uc,{})}));
