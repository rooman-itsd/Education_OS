(function(){const t=document.createElement("link").relList;if(t&&t.supports&&t.supports("modulepreload"))return;for(const r of document.querySelectorAll('link[rel="modulepreload"]'))i(r);new MutationObserver(r=>{for(const s of r)if(s.type==="childList")for(const o of s.addedNodes)o.tagName==="LINK"&&o.rel==="modulepreload"&&i(o)}).observe(document,{childList:!0,subtree:!0});function n(r){const s={};return r.integrity&&(s.integrity=r.integrity),r.referrerPolicy&&(s.referrerPolicy=r.referrerPolicy),r.crossOrigin==="use-credentials"?s.credentials="include":r.crossOrigin==="anonymous"?s.credentials="omit":s.credentials="same-origin",s}function i(r){if(r.ep)return;r.ep=!0;const s=n(r);fetch(r.href,s)}})();function Ud(e){return e&&e.__esModule&&Object.prototype.hasOwnProperty.call(e,"default")?e.default:e}var Uc={exports:{}},os={},Kc={exports:{}},x={};/**
 * @license React
 * react.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */var Fi=Symbol.for("react.element"),Kd=Symbol.for("react.portal"),Wd=Symbol.for("react.fragment"),qd=Symbol.for("react.strict_mode"),Qd=Symbol.for("react.profiler"),Gd=Symbol.for("react.provider"),Yd=Symbol.for("react.context"),Jd=Symbol.for("react.forward_ref"),Xd=Symbol.for("react.suspense"),Zd=Symbol.for("react.memo"),ep=Symbol.for("react.lazy"),bl=Symbol.iterator;function tp(e){return e===null||typeof e!="object"?null:(e=bl&&e[bl]||e["@@iterator"],typeof e=="function"?e:null)}var Wc={isMounted:function(){return!1},enqueueForceUpdate:function(){},enqueueReplaceState:function(){},enqueueSetState:function(){}},qc=Object.assign,Qc={};function $n(e,t,n){this.props=e,this.context=t,this.refs=Qc,this.updater=n||Wc}$n.prototype.isReactComponent={};$n.prototype.setState=function(e,t){if(typeof e!="object"&&typeof e!="function"&&e!=null)throw Error("setState(...): takes an object of state variables to update or a function which returns an object of state variables.");this.updater.enqueueSetState(this,e,t,"setState")};$n.prototype.forceUpdate=function(e){this.updater.enqueueForceUpdate(this,e,"forceUpdate")};function Gc(){}Gc.prototype=$n.prototype;function pa(e,t,n){this.props=e,this.context=t,this.refs=Qc,this.updater=n||Wc}var ha=pa.prototype=new Gc;ha.constructor=pa;qc(ha,$n.prototype);ha.isPureReactComponent=!0;var El=Array.isArray,Yc=Object.prototype.hasOwnProperty,ma={current:null},Jc={key:!0,ref:!0,__self:!0,__source:!0};function Xc(e,t,n){var i,r={},s=null,o=null;if(t!=null)for(i in t.ref!==void 0&&(o=t.ref),t.key!==void 0&&(s=""+t.key),t)Yc.call(t,i)&&!Jc.hasOwnProperty(i)&&(r[i]=t[i]);var a=arguments.length-2;if(a===1)r.children=n;else if(1<a){for(var l=Array(a),c=0;c<a;c++)l[c]=arguments[c+2];r.children=l}if(e&&e.defaultProps)for(i in a=e.defaultProps,a)r[i]===void 0&&(r[i]=a[i]);return{$$typeof:Fi,type:e,key:s,ref:o,props:r,_owner:ma.current}}function np(e,t){return{$$typeof:Fi,type:e.type,key:t,ref:e.ref,props:e.props,_owner:e._owner}}function ga(e){return typeof e=="object"&&e!==null&&e.$$typeof===Fi}function ip(e){var t={"=":"=0",":":"=2"};return"$"+e.replace(/[=:]/g,function(n){return t[n]})}var Cl=/\/+/g;function Rs(e,t){return typeof e=="object"&&e!==null&&e.key!=null?ip(""+e.key):t.toString(36)}function vr(e,t,n,i,r){var s=typeof e;(s==="undefined"||s==="boolean")&&(e=null);var o=!1;if(e===null)o=!0;else switch(s){case"string":case"number":o=!0;break;case"object":switch(e.$$typeof){case Fi:case Kd:o=!0}}if(o)return o=e,r=r(o),e=i===""?"."+Rs(o,0):i,El(r)?(n="",e!=null&&(n=e.replace(Cl,"$&/")+"/"),vr(r,t,n,"",function(c){return c})):r!=null&&(ga(r)&&(r=np(r,n+(!r.key||o&&o.key===r.key?"":(""+r.key).replace(Cl,"$&/")+"/")+e)),t.push(r)),1;if(o=0,i=i===""?".":i+":",El(e))for(var a=0;a<e.length;a++){s=e[a];var l=i+Rs(s,a);o+=vr(s,t,n,l,r)}else if(l=tp(e),typeof l=="function")for(e=l.call(e),a=0;!(s=e.next()).done;)s=s.value,l=i+Rs(s,a++),o+=vr(s,t,n,l,r);else if(s==="object")throw t=String(e),Error("Objects are not valid as a React child (found: "+(t==="[object Object]"?"object with keys {"+Object.keys(e).join(", ")+"}":t)+"). If you meant to render a collection of children, use an array instead.");return o}function Yi(e,t,n){if(e==null)return e;var i=[],r=0;return vr(e,i,"","",function(s){return t.call(n,s,r++)}),i}function rp(e){if(e._status===-1){var t=e._result;t=t(),t.then(function(n){(e._status===0||e._status===-1)&&(e._status=1,e._result=n)},function(n){(e._status===0||e._status===-1)&&(e._status=2,e._result=n)}),e._status===-1&&(e._status=0,e._result=t)}if(e._status===1)return e._result.default;throw e._result}var ve={current:null},wr={transition:null},sp={ReactCurrentDispatcher:ve,ReactCurrentBatchConfig:wr,ReactCurrentOwner:ma};function Zc(){throw Error("act(...) is not supported in production builds of React.")}x.Children={map:Yi,forEach:function(e,t,n){Yi(e,function(){t.apply(this,arguments)},n)},count:function(e){var t=0;return Yi(e,function(){t++}),t},toArray:function(e){return Yi(e,function(t){return t})||[]},only:function(e){if(!ga(e))throw Error("React.Children.only expected to receive a single React element child.");return e}};x.Component=$n;x.Fragment=Wd;x.Profiler=Qd;x.PureComponent=pa;x.StrictMode=qd;x.Suspense=Xd;x.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED=sp;x.act=Zc;x.cloneElement=function(e,t,n){if(e==null)throw Error("React.cloneElement(...): The argument must be a React element, but you passed "+e+".");var i=qc({},e.props),r=e.key,s=e.ref,o=e._owner;if(t!=null){if(t.ref!==void 0&&(s=t.ref,o=ma.current),t.key!==void 0&&(r=""+t.key),e.type&&e.type.defaultProps)var a=e.type.defaultProps;for(l in t)Yc.call(t,l)&&!Jc.hasOwnProperty(l)&&(i[l]=t[l]===void 0&&a!==void 0?a[l]:t[l])}var l=arguments.length-2;if(l===1)i.children=n;else if(1<l){a=Array(l);for(var c=0;c<l;c++)a[c]=arguments[c+2];i.children=a}return{$$typeof:Fi,type:e.type,key:r,ref:s,props:i,_owner:o}};x.createContext=function(e){return e={$$typeof:Yd,_currentValue:e,_currentValue2:e,_threadCount:0,Provider:null,Consumer:null,_defaultValue:null,_globalName:null},e.Provider={$$typeof:Gd,_context:e},e.Consumer=e};x.createElement=Xc;x.createFactory=function(e){var t=Xc.bind(null,e);return t.type=e,t};x.createRef=function(){return{current:null}};x.forwardRef=function(e){return{$$typeof:Jd,render:e}};x.isValidElement=ga;x.lazy=function(e){return{$$typeof:ep,_payload:{_status:-1,_result:e},_init:rp}};x.memo=function(e,t){return{$$typeof:Zd,type:e,compare:t===void 0?null:t}};x.startTransition=function(e){var t=wr.transition;wr.transition={};try{e()}finally{wr.transition=t}};x.unstable_act=Zc;x.useCallback=function(e,t){return ve.current.useCallback(e,t)};x.useContext=function(e){return ve.current.useContext(e)};x.useDebugValue=function(){};x.useDeferredValue=function(e){return ve.current.useDeferredValue(e)};x.useEffect=function(e,t){return ve.current.useEffect(e,t)};x.useId=function(){return ve.current.useId()};x.useImperativeHandle=function(e,t,n){return ve.current.useImperativeHandle(e,t,n)};x.useInsertionEffect=function(e,t){return ve.current.useInsertionEffect(e,t)};x.useLayoutEffect=function(e,t){return ve.current.useLayoutEffect(e,t)};x.useMemo=function(e,t){return ve.current.useMemo(e,t)};x.useReducer=function(e,t,n){return ve.current.useReducer(e,t,n)};x.useRef=function(e){return ve.current.useRef(e)};x.useState=function(e){return ve.current.useState(e)};x.useSyncExternalStore=function(e,t,n){return ve.current.useSyncExternalStore(e,t,n)};x.useTransition=function(){return ve.current.useTransition()};x.version="18.3.1";Kc.exports=x;var Kt=Kc.exports;const a0=Ud(Kt);/**
 * @license React
 * react-jsx-runtime.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */var op=Kt,ap=Symbol.for("react.element"),lp=Symbol.for("react.fragment"),cp=Object.prototype.hasOwnProperty,up=op.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner,fp={key:!0,ref:!0,__self:!0,__source:!0};function eu(e,t,n){var i,r={},s=null,o=null;n!==void 0&&(s=""+n),t.key!==void 0&&(s=""+t.key),t.ref!==void 0&&(o=t.ref);for(i in t)cp.call(t,i)&&!fp.hasOwnProperty(i)&&(r[i]=t[i]);if(e&&e.defaultProps)for(i in t=e.defaultProps,t)r[i]===void 0&&(r[i]=t[i]);return{$$typeof:ap,type:e,key:s,ref:o,props:r,_owner:up.current}}os.Fragment=lp;os.jsx=eu;os.jsxs=eu;Uc.exports=os;var W=Uc.exports,Ml={},tu={exports:{}},Te={},nu={exports:{}},iu={};/**
 * @license React
 * scheduler.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */(function(e){function t(N,L){var D=N.length;N.push(L);e:for(;0<D;){var Q=D-1>>>1,ne=N[Q];if(0<r(ne,L))N[Q]=L,N[D]=ne,D=Q;else break e}}function n(N){return N.length===0?null:N[0]}function i(N){if(N.length===0)return null;var L=N[0],D=N.pop();if(D!==L){N[0]=D;e:for(var Q=0,ne=N.length,Qi=ne>>>1;Q<Qi;){var Rt=2*(Q+1)-1,xs=N[Rt],Pt=Rt+1,Gi=N[Pt];if(0>r(xs,D))Pt<ne&&0>r(Gi,xs)?(N[Q]=Gi,N[Pt]=D,Q=Pt):(N[Q]=xs,N[Rt]=D,Q=Rt);else if(Pt<ne&&0>r(Gi,D))N[Q]=Gi,N[Pt]=D,Q=Pt;else break e}}return L}function r(N,L){var D=N.sortIndex-L.sortIndex;return D!==0?D:N.id-L.id}if(typeof performance=="object"&&typeof performance.now=="function"){var s=performance;e.unstable_now=function(){return s.now()}}else{var o=Date,a=o.now();e.unstable_now=function(){return o.now()-a}}var l=[],c=[],h=1,u=null,p=3,g=!1,v=!1,y=!1,k=typeof setTimeout=="function"?setTimeout:null,d=typeof clearTimeout=="function"?clearTimeout:null,f=typeof setImmediate<"u"?setImmediate:null;typeof navigator<"u"&&navigator.scheduling!==void 0&&navigator.scheduling.isInputPending!==void 0&&navigator.scheduling.isInputPending.bind(navigator.scheduling);function m(N){for(var L=n(c);L!==null;){if(L.callback===null)i(c);else if(L.startTime<=N)i(c),L.sortIndex=L.expirationTime,t(l,L);else break;L=n(c)}}function w(N){if(y=!1,m(N),!v)if(n(l)!==null)v=!0,Ls(S);else{var L=n(c);L!==null&&Ds(w,L.startTime-N)}}function S(N,L){v=!1,y&&(y=!1,d(_),_=-1),g=!0;var D=p;try{for(m(L),u=n(l);u!==null&&(!(u.expirationTime>L)||N&&!q());){var Q=u.callback;if(typeof Q=="function"){u.callback=null,p=u.priorityLevel;var ne=Q(u.expirationTime<=L);L=e.unstable_now(),typeof ne=="function"?u.callback=ne:u===n(l)&&i(l),m(L)}else i(l);u=n(l)}if(u!==null)var Qi=!0;else{var Rt=n(c);Rt!==null&&Ds(w,Rt.startTime-L),Qi=!1}return Qi}finally{u=null,p=D,g=!1}}var M=!1,E=null,_=-1,I=5,T=-1;function q(){return!(e.unstable_now()-T<I)}function se(){if(E!==null){var N=e.unstable_now();T=N;var L=!0;try{L=E(!0,N)}finally{L?oe():(M=!1,E=null)}}else M=!1}var oe;if(typeof f=="function")oe=function(){f(se)};else if(typeof MessageChannel<"u"){var Wn=new MessageChannel,Vd=Wn.port2;Wn.port1.onmessage=se,oe=function(){Vd.postMessage(null)}}else oe=function(){k(se,0)};function Ls(N){E=N,M||(M=!0,oe())}function Ds(N,L){_=k(function(){N(e.unstable_now())},L)}e.unstable_IdlePriority=5,e.unstable_ImmediatePriority=1,e.unstable_LowPriority=4,e.unstable_NormalPriority=3,e.unstable_Profiling=null,e.unstable_UserBlockingPriority=2,e.unstable_cancelCallback=function(N){N.callback=null},e.unstable_continueExecution=function(){v||g||(v=!0,Ls(S))},e.unstable_forceFrameRate=function(N){0>N||125<N?console.error("forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported"):I=0<N?Math.floor(1e3/N):5},e.unstable_getCurrentPriorityLevel=function(){return p},e.unstable_getFirstCallbackNode=function(){return n(l)},e.unstable_next=function(N){switch(p){case 1:case 2:case 3:var L=3;break;default:L=p}var D=p;p=L;try{return N()}finally{p=D}},e.unstable_pauseExecution=function(){},e.unstable_requestPaint=function(){},e.unstable_runWithPriority=function(N,L){switch(N){case 1:case 2:case 3:case 4:case 5:break;default:N=3}var D=p;p=N;try{return L()}finally{p=D}},e.unstable_scheduleCallback=function(N,L,D){var Q=e.unstable_now();switch(typeof D=="object"&&D!==null?(D=D.delay,D=typeof D=="number"&&0<D?Q+D:Q):D=Q,N){case 1:var ne=-1;break;case 2:ne=250;break;case 5:ne=1073741823;break;case 4:ne=1e4;break;default:ne=5e3}return ne=D+ne,N={id:h++,callback:L,priorityLevel:N,startTime:D,expirationTime:ne,sortIndex:-1},D>Q?(N.sortIndex=D,t(c,N),n(l)===null&&N===n(c)&&(y?(d(_),_=-1):y=!0,Ds(w,D-Q))):(N.sortIndex=ne,t(l,N),v||g||(v=!0,Ls(S))),N},e.unstable_shouldYield=q,e.unstable_wrapCallback=function(N){var L=p;return function(){var D=p;p=L;try{return N.apply(this,arguments)}finally{p=D}}}})(iu);nu.exports=iu;var dp=nu.exports;/**
 * @license React
 * react-dom.production.min.js
 *
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */var pp=Kt,Ne=dp;function C(e){for(var t="https://reactjs.org/docs/error-decoder.html?invariant="+e,n=1;n<arguments.length;n++)t+="&args[]="+encodeURIComponent(arguments[n]);return"Minified React error #"+e+"; visit "+t+" for the full message or use the non-minified dev environment for full errors and additional helpful warnings."}var ru=new Set,ki={};function en(e,t){Tn(e,t),Tn(e+"Capture",t)}function Tn(e,t){for(ki[e]=t,e=0;e<t.length;e++)ru.add(t[e])}var lt=!(typeof window>"u"||typeof window.document>"u"||typeof window.document.createElement>"u"),ho=Object.prototype.hasOwnProperty,hp=/^[:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD][:A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF\uF900-\uFDCF\uFDF0-\uFFFD\-.0-9\u00B7\u0300-\u036F\u203F-\u2040]*$/,Al={},Nl={};function mp(e){return ho.call(Nl,e)?!0:ho.call(Al,e)?!1:hp.test(e)?Nl[e]=!0:(Al[e]=!0,!1)}function gp(e,t,n,i){if(n!==null&&n.type===0)return!1;switch(typeof t){case"function":case"symbol":return!0;case"boolean":return i?!1:n!==null?!n.acceptsBooleans:(e=e.toLowerCase().slice(0,5),e!=="data-"&&e!=="aria-");default:return!1}}function yp(e,t,n,i){if(t===null||typeof t>"u"||gp(e,t,n,i))return!0;if(i)return!1;if(n!==null)switch(n.type){case 3:return!t;case 4:return t===!1;case 5:return isNaN(t);case 6:return isNaN(t)||1>t}return!1}function we(e,t,n,i,r,s,o){this.acceptsBooleans=t===2||t===3||t===4,this.attributeName=i,this.attributeNamespace=r,this.mustUseProperty=n,this.propertyName=e,this.type=t,this.sanitizeURL=s,this.removeEmptyString=o}var ce={};"children dangerouslySetInnerHTML defaultValue defaultChecked innerHTML suppressContentEditableWarning suppressHydrationWarning style".split(" ").forEach(function(e){ce[e]=new we(e,0,!1,e,null,!1,!1)});[["acceptCharset","accept-charset"],["className","class"],["htmlFor","for"],["httpEquiv","http-equiv"]].forEach(function(e){var t=e[0];ce[t]=new we(t,1,!1,e[1],null,!1,!1)});["contentEditable","draggable","spellCheck","value"].forEach(function(e){ce[e]=new we(e,2,!1,e.toLowerCase(),null,!1,!1)});["autoReverse","externalResourcesRequired","focusable","preserveAlpha"].forEach(function(e){ce[e]=new we(e,2,!1,e,null,!1,!1)});"allowFullScreen async autoFocus autoPlay controls default defer disabled disablePictureInPicture disableRemotePlayback formNoValidate hidden loop noModule noValidate open playsInline readOnly required reversed scoped seamless itemScope".split(" ").forEach(function(e){ce[e]=new we(e,3,!1,e.toLowerCase(),null,!1,!1)});["checked","multiple","muted","selected"].forEach(function(e){ce[e]=new we(e,3,!0,e,null,!1,!1)});["capture","download"].forEach(function(e){ce[e]=new we(e,4,!1,e,null,!1,!1)});["cols","rows","size","span"].forEach(function(e){ce[e]=new we(e,6,!1,e,null,!1,!1)});["rowSpan","start"].forEach(function(e){ce[e]=new we(e,5,!1,e.toLowerCase(),null,!1,!1)});var ya=/[\-:]([a-z])/g;function va(e){return e[1].toUpperCase()}"accent-height alignment-baseline arabic-form baseline-shift cap-height clip-path clip-rule color-interpolation color-interpolation-filters color-profile color-rendering dominant-baseline enable-background fill-opacity fill-rule flood-color flood-opacity font-family font-size font-size-adjust font-stretch font-style font-variant font-weight glyph-name glyph-orientation-horizontal glyph-orientation-vertical horiz-adv-x horiz-origin-x image-rendering letter-spacing lighting-color marker-end marker-mid marker-start overline-position overline-thickness paint-order panose-1 pointer-events rendering-intent shape-rendering stop-color stop-opacity strikethrough-position strikethrough-thickness stroke-dasharray stroke-dashoffset stroke-linecap stroke-linejoin stroke-miterlimit stroke-opacity stroke-width text-anchor text-decoration text-rendering underline-position underline-thickness unicode-bidi unicode-range units-per-em v-alphabetic v-hanging v-ideographic v-mathematical vector-effect vert-adv-y vert-origin-x vert-origin-y word-spacing writing-mode xmlns:xlink x-height".split(" ").forEach(function(e){var t=e.replace(ya,va);ce[t]=new we(t,1,!1,e,null,!1,!1)});"xlink:actuate xlink:arcrole xlink:role xlink:show xlink:title xlink:type".split(" ").forEach(function(e){var t=e.replace(ya,va);ce[t]=new we(t,1,!1,e,"http://www.w3.org/1999/xlink",!1,!1)});["xml:base","xml:lang","xml:space"].forEach(function(e){var t=e.replace(ya,va);ce[t]=new we(t,1,!1,e,"http://www.w3.org/XML/1998/namespace",!1,!1)});["tabIndex","crossOrigin"].forEach(function(e){ce[e]=new we(e,1,!1,e.toLowerCase(),null,!1,!1)});ce.xlinkHref=new we("xlinkHref",1,!1,"xlink:href","http://www.w3.org/1999/xlink",!0,!1);["src","href","action","formAction"].forEach(function(e){ce[e]=new we(e,1,!1,e.toLowerCase(),null,!0,!0)});function wa(e,t,n,i){var r=ce.hasOwnProperty(t)?ce[t]:null;(r!==null?r.type!==0:i||!(2<t.length)||t[0]!=="o"&&t[0]!=="O"||t[1]!=="n"&&t[1]!=="N")&&(yp(t,n,r,i)&&(n=null),i||r===null?mp(t)&&(n===null?e.removeAttribute(t):e.setAttribute(t,""+n)):r.mustUseProperty?e[r.propertyName]=n===null?r.type===3?!1:"":n:(t=r.attributeName,i=r.attributeNamespace,n===null?e.removeAttribute(t):(r=r.type,n=r===3||r===4&&n===!0?"":""+n,i?e.setAttributeNS(i,t,n):e.setAttribute(t,n))))}var dt=pp.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED,Ji=Symbol.for("react.element"),on=Symbol.for("react.portal"),an=Symbol.for("react.fragment"),ka=Symbol.for("react.strict_mode"),mo=Symbol.for("react.profiler"),su=Symbol.for("react.provider"),ou=Symbol.for("react.context"),Sa=Symbol.for("react.forward_ref"),go=Symbol.for("react.suspense"),yo=Symbol.for("react.suspense_list"),_a=Symbol.for("react.memo"),ht=Symbol.for("react.lazy"),au=Symbol.for("react.offscreen"),Tl=Symbol.iterator;function qn(e){return e===null||typeof e!="object"?null:(e=Tl&&e[Tl]||e["@@iterator"],typeof e=="function"?e:null)}var U=Object.assign,Ps;function ni(e){if(Ps===void 0)try{throw Error()}catch(n){var t=n.stack.trim().match(/\n( *(at )?)/);Ps=t&&t[1]||""}return`
`+Ps+e}var js=!1;function $s(e,t){if(!e||js)return"";js=!0;var n=Error.prepareStackTrace;Error.prepareStackTrace=void 0;try{if(t)if(t=function(){throw Error()},Object.defineProperty(t.prototype,"props",{set:function(){throw Error()}}),typeof Reflect=="object"&&Reflect.construct){try{Reflect.construct(t,[])}catch(c){var i=c}Reflect.construct(e,[],t)}else{try{t.call()}catch(c){i=c}e.call(t.prototype)}else{try{throw Error()}catch(c){i=c}e()}}catch(c){if(c&&i&&typeof c.stack=="string"){for(var r=c.stack.split(`
`),s=i.stack.split(`
`),o=r.length-1,a=s.length-1;1<=o&&0<=a&&r[o]!==s[a];)a--;for(;1<=o&&0<=a;o--,a--)if(r[o]!==s[a]){if(o!==1||a!==1)do if(o--,a--,0>a||r[o]!==s[a]){var l=`
`+r[o].replace(" at new "," at ");return e.displayName&&l.includes("<anonymous>")&&(l=l.replace("<anonymous>",e.displayName)),l}while(1<=o&&0<=a);break}}}finally{js=!1,Error.prepareStackTrace=n}return(e=e?e.displayName||e.name:"")?ni(e):""}function vp(e){switch(e.tag){case 5:return ni(e.type);case 16:return ni("Lazy");case 13:return ni("Suspense");case 19:return ni("SuspenseList");case 0:case 2:case 15:return e=$s(e.type,!1),e;case 11:return e=$s(e.type.render,!1),e;case 1:return e=$s(e.type,!0),e;default:return""}}function vo(e){if(e==null)return null;if(typeof e=="function")return e.displayName||e.name||null;if(typeof e=="string")return e;switch(e){case an:return"Fragment";case on:return"Portal";case mo:return"Profiler";case ka:return"StrictMode";case go:return"Suspense";case yo:return"SuspenseList"}if(typeof e=="object")switch(e.$$typeof){case ou:return(e.displayName||"Context")+".Consumer";case su:return(e._context.displayName||"Context")+".Provider";case Sa:var t=e.render;return e=e.displayName,e||(e=t.displayName||t.name||"",e=e!==""?"ForwardRef("+e+")":"ForwardRef"),e;case _a:return t=e.displayName||null,t!==null?t:vo(e.type)||"Memo";case ht:t=e._payload,e=e._init;try{return vo(e(t))}catch{}}return null}function wp(e){var t=e.type;switch(e.tag){case 24:return"Cache";case 9:return(t.displayName||"Context")+".Consumer";case 10:return(t._context.displayName||"Context")+".Provider";case 18:return"DehydratedFragment";case 11:return e=t.render,e=e.displayName||e.name||"",t.displayName||(e!==""?"ForwardRef("+e+")":"ForwardRef");case 7:return"Fragment";case 5:return t;case 4:return"Portal";case 3:return"Root";case 6:return"Text";case 16:return vo(t);case 8:return t===ka?"StrictMode":"Mode";case 22:return"Offscreen";case 12:return"Profiler";case 21:return"Scope";case 13:return"Suspense";case 19:return"SuspenseList";case 25:return"TracingMarker";case 1:case 0:case 17:case 2:case 14:case 15:if(typeof t=="function")return t.displayName||t.name||null;if(typeof t=="string")return t}return null}function It(e){switch(typeof e){case"boolean":case"number":case"string":case"undefined":return e;case"object":return e;default:return""}}function lu(e){var t=e.type;return(e=e.nodeName)&&e.toLowerCase()==="input"&&(t==="checkbox"||t==="radio")}function kp(e){var t=lu(e)?"checked":"value",n=Object.getOwnPropertyDescriptor(e.constructor.prototype,t),i=""+e[t];if(!e.hasOwnProperty(t)&&typeof n<"u"&&typeof n.get=="function"&&typeof n.set=="function"){var r=n.get,s=n.set;return Object.defineProperty(e,t,{configurable:!0,get:function(){return r.call(this)},set:function(o){i=""+o,s.call(this,o)}}),Object.defineProperty(e,t,{enumerable:n.enumerable}),{getValue:function(){return i},setValue:function(o){i=""+o},stopTracking:function(){e._valueTracker=null,delete e[t]}}}}function Xi(e){e._valueTracker||(e._valueTracker=kp(e))}function cu(e){if(!e)return!1;var t=e._valueTracker;if(!t)return!0;var n=t.getValue(),i="";return e&&(i=lu(e)?e.checked?"true":"false":e.value),e=i,e!==n?(t.setValue(e),!0):!1}function Dr(e){if(e=e||(typeof document<"u"?document:void 0),typeof e>"u")return null;try{return e.activeElement||e.body}catch{return e.body}}function wo(e,t){var n=t.checked;return U({},t,{defaultChecked:void 0,defaultValue:void 0,value:void 0,checked:n??e._wrapperState.initialChecked})}function Il(e,t){var n=t.defaultValue==null?"":t.defaultValue,i=t.checked!=null?t.checked:t.defaultChecked;n=It(t.value!=null?t.value:n),e._wrapperState={initialChecked:i,initialValue:n,controlled:t.type==="checkbox"||t.type==="radio"?t.checked!=null:t.value!=null}}function uu(e,t){t=t.checked,t!=null&&wa(e,"checked",t,!1)}function ko(e,t){uu(e,t);var n=It(t.value),i=t.type;if(n!=null)i==="number"?(n===0&&e.value===""||e.value!=n)&&(e.value=""+n):e.value!==""+n&&(e.value=""+n);else if(i==="submit"||i==="reset"){e.removeAttribute("value");return}t.hasOwnProperty("value")?So(e,t.type,n):t.hasOwnProperty("defaultValue")&&So(e,t.type,It(t.defaultValue)),t.checked==null&&t.defaultChecked!=null&&(e.defaultChecked=!!t.defaultChecked)}function Ol(e,t,n){if(t.hasOwnProperty("value")||t.hasOwnProperty("defaultValue")){var i=t.type;if(!(i!=="submit"&&i!=="reset"||t.value!==void 0&&t.value!==null))return;t=""+e._wrapperState.initialValue,n||t===e.value||(e.value=t),e.defaultValue=t}n=e.name,n!==""&&(e.name=""),e.defaultChecked=!!e._wrapperState.initialChecked,n!==""&&(e.name=n)}function So(e,t,n){(t!=="number"||Dr(e.ownerDocument)!==e)&&(n==null?e.defaultValue=""+e._wrapperState.initialValue:e.defaultValue!==""+n&&(e.defaultValue=""+n))}var ii=Array.isArray;function Sn(e,t,n,i){if(e=e.options,t){t={};for(var r=0;r<n.length;r++)t["$"+n[r]]=!0;for(n=0;n<e.length;n++)r=t.hasOwnProperty("$"+e[n].value),e[n].selected!==r&&(e[n].selected=r),r&&i&&(e[n].defaultSelected=!0)}else{for(n=""+It(n),t=null,r=0;r<e.length;r++){if(e[r].value===n){e[r].selected=!0,i&&(e[r].defaultSelected=!0);return}t!==null||e[r].disabled||(t=e[r])}t!==null&&(t.selected=!0)}}function _o(e,t){if(t.dangerouslySetInnerHTML!=null)throw Error(C(91));return U({},t,{value:void 0,defaultValue:void 0,children:""+e._wrapperState.initialValue})}function Ll(e,t){var n=t.value;if(n==null){if(n=t.children,t=t.defaultValue,n!=null){if(t!=null)throw Error(C(92));if(ii(n)){if(1<n.length)throw Error(C(93));n=n[0]}t=n}t==null&&(t=""),n=t}e._wrapperState={initialValue:It(n)}}function fu(e,t){var n=It(t.value),i=It(t.defaultValue);n!=null&&(n=""+n,n!==e.value&&(e.value=n),t.defaultValue==null&&e.defaultValue!==n&&(e.defaultValue=n)),i!=null&&(e.defaultValue=""+i)}function Dl(e){var t=e.textContent;t===e._wrapperState.initialValue&&t!==""&&t!==null&&(e.value=t)}function du(e){switch(e){case"svg":return"http://www.w3.org/2000/svg";case"math":return"http://www.w3.org/1998/Math/MathML";default:return"http://www.w3.org/1999/xhtml"}}function bo(e,t){return e==null||e==="http://www.w3.org/1999/xhtml"?du(t):e==="http://www.w3.org/2000/svg"&&t==="foreignObject"?"http://www.w3.org/1999/xhtml":e}var Zi,pu=function(e){return typeof MSApp<"u"&&MSApp.execUnsafeLocalFunction?function(t,n,i,r){MSApp.execUnsafeLocalFunction(function(){return e(t,n,i,r)})}:e}(function(e,t){if(e.namespaceURI!=="http://www.w3.org/2000/svg"||"innerHTML"in e)e.innerHTML=t;else{for(Zi=Zi||document.createElement("div"),Zi.innerHTML="<svg>"+t.valueOf().toString()+"</svg>",t=Zi.firstChild;e.firstChild;)e.removeChild(e.firstChild);for(;t.firstChild;)e.appendChild(t.firstChild)}});function Si(e,t){if(t){var n=e.firstChild;if(n&&n===e.lastChild&&n.nodeType===3){n.nodeValue=t;return}}e.textContent=t}var li={animationIterationCount:!0,aspectRatio:!0,borderImageOutset:!0,borderImageSlice:!0,borderImageWidth:!0,boxFlex:!0,boxFlexGroup:!0,boxOrdinalGroup:!0,columnCount:!0,columns:!0,flex:!0,flexGrow:!0,flexPositive:!0,flexShrink:!0,flexNegative:!0,flexOrder:!0,gridArea:!0,gridRow:!0,gridRowEnd:!0,gridRowSpan:!0,gridRowStart:!0,gridColumn:!0,gridColumnEnd:!0,gridColumnSpan:!0,gridColumnStart:!0,fontWeight:!0,lineClamp:!0,lineHeight:!0,opacity:!0,order:!0,orphans:!0,tabSize:!0,widows:!0,zIndex:!0,zoom:!0,fillOpacity:!0,floodOpacity:!0,stopOpacity:!0,strokeDasharray:!0,strokeDashoffset:!0,strokeMiterlimit:!0,strokeOpacity:!0,strokeWidth:!0},Sp=["Webkit","ms","Moz","O"];Object.keys(li).forEach(function(e){Sp.forEach(function(t){t=t+e.charAt(0).toUpperCase()+e.substring(1),li[t]=li[e]})});function hu(e,t,n){return t==null||typeof t=="boolean"||t===""?"":n||typeof t!="number"||t===0||li.hasOwnProperty(e)&&li[e]?(""+t).trim():t+"px"}function mu(e,t){e=e.style;for(var n in t)if(t.hasOwnProperty(n)){var i=n.indexOf("--")===0,r=hu(n,t[n],i);n==="float"&&(n="cssFloat"),i?e.setProperty(n,r):e[n]=r}}var _p=U({menuitem:!0},{area:!0,base:!0,br:!0,col:!0,embed:!0,hr:!0,img:!0,input:!0,keygen:!0,link:!0,meta:!0,param:!0,source:!0,track:!0,wbr:!0});function Eo(e,t){if(t){if(_p[e]&&(t.children!=null||t.dangerouslySetInnerHTML!=null))throw Error(C(137,e));if(t.dangerouslySetInnerHTML!=null){if(t.children!=null)throw Error(C(60));if(typeof t.dangerouslySetInnerHTML!="object"||!("__html"in t.dangerouslySetInnerHTML))throw Error(C(61))}if(t.style!=null&&typeof t.style!="object")throw Error(C(62))}}function Co(e,t){if(e.indexOf("-")===-1)return typeof t.is=="string";switch(e){case"annotation-xml":case"color-profile":case"font-face":case"font-face-src":case"font-face-uri":case"font-face-format":case"font-face-name":case"missing-glyph":return!1;default:return!0}}var Mo=null;function ba(e){return e=e.target||e.srcElement||window,e.correspondingUseElement&&(e=e.correspondingUseElement),e.nodeType===3?e.parentNode:e}var Ao=null,_n=null,bn=null;function xl(e){if(e=Hi(e)){if(typeof Ao!="function")throw Error(C(280));var t=e.stateNode;t&&(t=fs(t),Ao(e.stateNode,e.type,t))}}function gu(e){_n?bn?bn.push(e):bn=[e]:_n=e}function yu(){if(_n){var e=_n,t=bn;if(bn=_n=null,xl(e),t)for(e=0;e<t.length;e++)xl(t[e])}}function vu(e,t){return e(t)}function wu(){}var Fs=!1;function ku(e,t,n){if(Fs)return e(t,n);Fs=!0;try{return vu(e,t,n)}finally{Fs=!1,(_n!==null||bn!==null)&&(wu(),yu())}}function _i(e,t){var n=e.stateNode;if(n===null)return null;var i=fs(n);if(i===null)return null;n=i[t];e:switch(t){case"onClick":case"onClickCapture":case"onDoubleClick":case"onDoubleClickCapture":case"onMouseDown":case"onMouseDownCapture":case"onMouseMove":case"onMouseMoveCapture":case"onMouseUp":case"onMouseUpCapture":case"onMouseEnter":(i=!i.disabled)||(e=e.type,i=!(e==="button"||e==="input"||e==="select"||e==="textarea")),e=!i;break e;default:e=!1}if(e)return null;if(n&&typeof n!="function")throw Error(C(231,t,typeof n));return n}var No=!1;if(lt)try{var Qn={};Object.defineProperty(Qn,"passive",{get:function(){No=!0}}),window.addEventListener("test",Qn,Qn),window.removeEventListener("test",Qn,Qn)}catch{No=!1}function bp(e,t,n,i,r,s,o,a,l){var c=Array.prototype.slice.call(arguments,3);try{t.apply(n,c)}catch(h){this.onError(h)}}var ci=!1,xr=null,Rr=!1,To=null,Ep={onError:function(e){ci=!0,xr=e}};function Cp(e,t,n,i,r,s,o,a,l){ci=!1,xr=null,bp.apply(Ep,arguments)}function Mp(e,t,n,i,r,s,o,a,l){if(Cp.apply(this,arguments),ci){if(ci){var c=xr;ci=!1,xr=null}else throw Error(C(198));Rr||(Rr=!0,To=c)}}function tn(e){var t=e,n=e;if(e.alternate)for(;t.return;)t=t.return;else{e=t;do t=e,t.flags&4098&&(n=t.return),e=t.return;while(e)}return t.tag===3?n:null}function Su(e){if(e.tag===13){var t=e.memoizedState;if(t===null&&(e=e.alternate,e!==null&&(t=e.memoizedState)),t!==null)return t.dehydrated}return null}function Rl(e){if(tn(e)!==e)throw Error(C(188))}function Ap(e){var t=e.alternate;if(!t){if(t=tn(e),t===null)throw Error(C(188));return t!==e?null:e}for(var n=e,i=t;;){var r=n.return;if(r===null)break;var s=r.alternate;if(s===null){if(i=r.return,i!==null){n=i;continue}break}if(r.child===s.child){for(s=r.child;s;){if(s===n)return Rl(r),e;if(s===i)return Rl(r),t;s=s.sibling}throw Error(C(188))}if(n.return!==i.return)n=r,i=s;else{for(var o=!1,a=r.child;a;){if(a===n){o=!0,n=r,i=s;break}if(a===i){o=!0,i=r,n=s;break}a=a.sibling}if(!o){for(a=s.child;a;){if(a===n){o=!0,n=s,i=r;break}if(a===i){o=!0,i=s,n=r;break}a=a.sibling}if(!o)throw Error(C(189))}}if(n.alternate!==i)throw Error(C(190))}if(n.tag!==3)throw Error(C(188));return n.stateNode.current===n?e:t}function _u(e){return e=Ap(e),e!==null?bu(e):null}function bu(e){if(e.tag===5||e.tag===6)return e;for(e=e.child;e!==null;){var t=bu(e);if(t!==null)return t;e=e.sibling}return null}var Eu=Ne.unstable_scheduleCallback,Pl=Ne.unstable_cancelCallback,Np=Ne.unstable_shouldYield,Tp=Ne.unstable_requestPaint,G=Ne.unstable_now,Ip=Ne.unstable_getCurrentPriorityLevel,Ea=Ne.unstable_ImmediatePriority,Cu=Ne.unstable_UserBlockingPriority,Pr=Ne.unstable_NormalPriority,Op=Ne.unstable_LowPriority,Mu=Ne.unstable_IdlePriority,as=null,Xe=null;function Lp(e){if(Xe&&typeof Xe.onCommitFiberRoot=="function")try{Xe.onCommitFiberRoot(as,e,void 0,(e.current.flags&128)===128)}catch{}}var Ke=Math.clz32?Math.clz32:Rp,Dp=Math.log,xp=Math.LN2;function Rp(e){return e>>>=0,e===0?32:31-(Dp(e)/xp|0)|0}var er=64,tr=4194304;function ri(e){switch(e&-e){case 1:return 1;case 2:return 2;case 4:return 4;case 8:return 8;case 16:return 16;case 32:return 32;case 64:case 128:case 256:case 512:case 1024:case 2048:case 4096:case 8192:case 16384:case 32768:case 65536:case 131072:case 262144:case 524288:case 1048576:case 2097152:return e&4194240;case 4194304:case 8388608:case 16777216:case 33554432:case 67108864:return e&130023424;case 134217728:return 134217728;case 268435456:return 268435456;case 536870912:return 536870912;case 1073741824:return 1073741824;default:return e}}function jr(e,t){var n=e.pendingLanes;if(n===0)return 0;var i=0,r=e.suspendedLanes,s=e.pingedLanes,o=n&268435455;if(o!==0){var a=o&~r;a!==0?i=ri(a):(s&=o,s!==0&&(i=ri(s)))}else o=n&~r,o!==0?i=ri(o):s!==0&&(i=ri(s));if(i===0)return 0;if(t!==0&&t!==i&&!(t&r)&&(r=i&-i,s=t&-t,r>=s||r===16&&(s&4194240)!==0))return t;if(i&4&&(i|=n&16),t=e.entangledLanes,t!==0)for(e=e.entanglements,t&=i;0<t;)n=31-Ke(t),r=1<<n,i|=e[n],t&=~r;return i}function Pp(e,t){switch(e){case 1:case 2:case 4:return t+250;case 8:case 16:case 32:case 64:case 128:case 256:case 512:case 1024:case 2048:case 4096:case 8192:case 16384:case 32768:case 65536:case 131072:case 262144:case 524288:case 1048576:case 2097152:return t+5e3;case 4194304:case 8388608:case 16777216:case 33554432:case 67108864:return-1;case 134217728:case 268435456:case 536870912:case 1073741824:return-1;default:return-1}}function jp(e,t){for(var n=e.suspendedLanes,i=e.pingedLanes,r=e.expirationTimes,s=e.pendingLanes;0<s;){var o=31-Ke(s),a=1<<o,l=r[o];l===-1?(!(a&n)||a&i)&&(r[o]=Pp(a,t)):l<=t&&(e.expiredLanes|=a),s&=~a}}function Io(e){return e=e.pendingLanes&-1073741825,e!==0?e:e&1073741824?1073741824:0}function Au(){var e=er;return er<<=1,!(er&4194240)&&(er=64),e}function zs(e){for(var t=[],n=0;31>n;n++)t.push(e);return t}function zi(e,t,n){e.pendingLanes|=t,t!==536870912&&(e.suspendedLanes=0,e.pingedLanes=0),e=e.eventTimes,t=31-Ke(t),e[t]=n}function $p(e,t){var n=e.pendingLanes&~t;e.pendingLanes=t,e.suspendedLanes=0,e.pingedLanes=0,e.expiredLanes&=t,e.mutableReadLanes&=t,e.entangledLanes&=t,t=e.entanglements;var i=e.eventTimes;for(e=e.expirationTimes;0<n;){var r=31-Ke(n),s=1<<r;t[r]=0,i[r]=-1,e[r]=-1,n&=~s}}function Ca(e,t){var n=e.entangledLanes|=t;for(e=e.entanglements;n;){var i=31-Ke(n),r=1<<i;r&t|e[i]&t&&(e[i]|=t),n&=~r}}var P=0;function Nu(e){return e&=-e,1<e?4<e?e&268435455?16:536870912:4:1}var Tu,Ma,Iu,Ou,Lu,Oo=!1,nr=[],St=null,_t=null,bt=null,bi=new Map,Ei=new Map,yt=[],Fp="mousedown mouseup touchcancel touchend touchstart auxclick dblclick pointercancel pointerdown pointerup dragend dragstart drop compositionend compositionstart keydown keypress keyup input textInput copy cut paste click change contextmenu reset submit".split(" ");function jl(e,t){switch(e){case"focusin":case"focusout":St=null;break;case"dragenter":case"dragleave":_t=null;break;case"mouseover":case"mouseout":bt=null;break;case"pointerover":case"pointerout":bi.delete(t.pointerId);break;case"gotpointercapture":case"lostpointercapture":Ei.delete(t.pointerId)}}function Gn(e,t,n,i,r,s){return e===null||e.nativeEvent!==s?(e={blockedOn:t,domEventName:n,eventSystemFlags:i,nativeEvent:s,targetContainers:[r]},t!==null&&(t=Hi(t),t!==null&&Ma(t)),e):(e.eventSystemFlags|=i,t=e.targetContainers,r!==null&&t.indexOf(r)===-1&&t.push(r),e)}function zp(e,t,n,i,r){switch(t){case"focusin":return St=Gn(St,e,t,n,i,r),!0;case"dragenter":return _t=Gn(_t,e,t,n,i,r),!0;case"mouseover":return bt=Gn(bt,e,t,n,i,r),!0;case"pointerover":var s=r.pointerId;return bi.set(s,Gn(bi.get(s)||null,e,t,n,i,r)),!0;case"gotpointercapture":return s=r.pointerId,Ei.set(s,Gn(Ei.get(s)||null,e,t,n,i,r)),!0}return!1}function Du(e){var t=zt(e.target);if(t!==null){var n=tn(t);if(n!==null){if(t=n.tag,t===13){if(t=Su(n),t!==null){e.blockedOn=t,Lu(e.priority,function(){Iu(n)});return}}else if(t===3&&n.stateNode.current.memoizedState.isDehydrated){e.blockedOn=n.tag===3?n.stateNode.containerInfo:null;return}}}e.blockedOn=null}function kr(e){if(e.blockedOn!==null)return!1;for(var t=e.targetContainers;0<t.length;){var n=Lo(e.domEventName,e.eventSystemFlags,t[0],e.nativeEvent);if(n===null){n=e.nativeEvent;var i=new n.constructor(n.type,n);Mo=i,n.target.dispatchEvent(i),Mo=null}else return t=Hi(n),t!==null&&Ma(t),e.blockedOn=n,!1;t.shift()}return!0}function $l(e,t,n){kr(e)&&n.delete(t)}function Bp(){Oo=!1,St!==null&&kr(St)&&(St=null),_t!==null&&kr(_t)&&(_t=null),bt!==null&&kr(bt)&&(bt=null),bi.forEach($l),Ei.forEach($l)}function Yn(e,t){e.blockedOn===t&&(e.blockedOn=null,Oo||(Oo=!0,Ne.unstable_scheduleCallback(Ne.unstable_NormalPriority,Bp)))}function Ci(e){function t(r){return Yn(r,e)}if(0<nr.length){Yn(nr[0],e);for(var n=1;n<nr.length;n++){var i=nr[n];i.blockedOn===e&&(i.blockedOn=null)}}for(St!==null&&Yn(St,e),_t!==null&&Yn(_t,e),bt!==null&&Yn(bt,e),bi.forEach(t),Ei.forEach(t),n=0;n<yt.length;n++)i=yt[n],i.blockedOn===e&&(i.blockedOn=null);for(;0<yt.length&&(n=yt[0],n.blockedOn===null);)Du(n),n.blockedOn===null&&yt.shift()}var En=dt.ReactCurrentBatchConfig,$r=!0;function Hp(e,t,n,i){var r=P,s=En.transition;En.transition=null;try{P=1,Aa(e,t,n,i)}finally{P=r,En.transition=s}}function Vp(e,t,n,i){var r=P,s=En.transition;En.transition=null;try{P=4,Aa(e,t,n,i)}finally{P=r,En.transition=s}}function Aa(e,t,n,i){if($r){var r=Lo(e,t,n,i);if(r===null)Ys(e,t,i,Fr,n),jl(e,i);else if(zp(r,e,t,n,i))i.stopPropagation();else if(jl(e,i),t&4&&-1<Fp.indexOf(e)){for(;r!==null;){var s=Hi(r);if(s!==null&&Tu(s),s=Lo(e,t,n,i),s===null&&Ys(e,t,i,Fr,n),s===r)break;r=s}r!==null&&i.stopPropagation()}else Ys(e,t,i,null,n)}}var Fr=null;function Lo(e,t,n,i){if(Fr=null,e=ba(i),e=zt(e),e!==null)if(t=tn(e),t===null)e=null;else if(n=t.tag,n===13){if(e=Su(t),e!==null)return e;e=null}else if(n===3){if(t.stateNode.current.memoizedState.isDehydrated)return t.tag===3?t.stateNode.containerInfo:null;e=null}else t!==e&&(e=null);return Fr=e,null}function xu(e){switch(e){case"cancel":case"click":case"close":case"contextmenu":case"copy":case"cut":case"auxclick":case"dblclick":case"dragend":case"dragstart":case"drop":case"focusin":case"focusout":case"input":case"invalid":case"keydown":case"keypress":case"keyup":case"mousedown":case"mouseup":case"paste":case"pause":case"play":case"pointercancel":case"pointerdown":case"pointerup":case"ratechange":case"reset":case"resize":case"seeked":case"submit":case"touchcancel":case"touchend":case"touchstart":case"volumechange":case"change":case"selectionchange":case"textInput":case"compositionstart":case"compositionend":case"compositionupdate":case"beforeblur":case"afterblur":case"beforeinput":case"blur":case"fullscreenchange":case"focus":case"hashchange":case"popstate":case"select":case"selectstart":return 1;case"drag":case"dragenter":case"dragexit":case"dragleave":case"dragover":case"mousemove":case"mouseout":case"mouseover":case"pointermove":case"pointerout":case"pointerover":case"scroll":case"toggle":case"touchmove":case"wheel":case"mouseenter":case"mouseleave":case"pointerenter":case"pointerleave":return 4;case"message":switch(Ip()){case Ea:return 1;case Cu:return 4;case Pr:case Op:return 16;case Mu:return 536870912;default:return 16}default:return 16}}var wt=null,Na=null,Sr=null;function Ru(){if(Sr)return Sr;var e,t=Na,n=t.length,i,r="value"in wt?wt.value:wt.textContent,s=r.length;for(e=0;e<n&&t[e]===r[e];e++);var o=n-e;for(i=1;i<=o&&t[n-i]===r[s-i];i++);return Sr=r.slice(e,1<i?1-i:void 0)}function _r(e){var t=e.keyCode;return"charCode"in e?(e=e.charCode,e===0&&t===13&&(e=13)):e=t,e===10&&(e=13),32<=e||e===13?e:0}function ir(){return!0}function Fl(){return!1}function Ie(e){function t(n,i,r,s,o){this._reactName=n,this._targetInst=r,this.type=i,this.nativeEvent=s,this.target=o,this.currentTarget=null;for(var a in e)e.hasOwnProperty(a)&&(n=e[a],this[a]=n?n(s):s[a]);return this.isDefaultPrevented=(s.defaultPrevented!=null?s.defaultPrevented:s.returnValue===!1)?ir:Fl,this.isPropagationStopped=Fl,this}return U(t.prototype,{preventDefault:function(){this.defaultPrevented=!0;var n=this.nativeEvent;n&&(n.preventDefault?n.preventDefault():typeof n.returnValue!="unknown"&&(n.returnValue=!1),this.isDefaultPrevented=ir)},stopPropagation:function(){var n=this.nativeEvent;n&&(n.stopPropagation?n.stopPropagation():typeof n.cancelBubble!="unknown"&&(n.cancelBubble=!0),this.isPropagationStopped=ir)},persist:function(){},isPersistent:ir}),t}var Fn={eventPhase:0,bubbles:0,cancelable:0,timeStamp:function(e){return e.timeStamp||Date.now()},defaultPrevented:0,isTrusted:0},Ta=Ie(Fn),Bi=U({},Fn,{view:0,detail:0}),Up=Ie(Bi),Bs,Hs,Jn,ls=U({},Bi,{screenX:0,screenY:0,clientX:0,clientY:0,pageX:0,pageY:0,ctrlKey:0,shiftKey:0,altKey:0,metaKey:0,getModifierState:Ia,button:0,buttons:0,relatedTarget:function(e){return e.relatedTarget===void 0?e.fromElement===e.srcElement?e.toElement:e.fromElement:e.relatedTarget},movementX:function(e){return"movementX"in e?e.movementX:(e!==Jn&&(Jn&&e.type==="mousemove"?(Bs=e.screenX-Jn.screenX,Hs=e.screenY-Jn.screenY):Hs=Bs=0,Jn=e),Bs)},movementY:function(e){return"movementY"in e?e.movementY:Hs}}),zl=Ie(ls),Kp=U({},ls,{dataTransfer:0}),Wp=Ie(Kp),qp=U({},Bi,{relatedTarget:0}),Vs=Ie(qp),Qp=U({},Fn,{animationName:0,elapsedTime:0,pseudoElement:0}),Gp=Ie(Qp),Yp=U({},Fn,{clipboardData:function(e){return"clipboardData"in e?e.clipboardData:window.clipboardData}}),Jp=Ie(Yp),Xp=U({},Fn,{data:0}),Bl=Ie(Xp),Zp={Esc:"Escape",Spacebar:" ",Left:"ArrowLeft",Up:"ArrowUp",Right:"ArrowRight",Down:"ArrowDown",Del:"Delete",Win:"OS",Menu:"ContextMenu",Apps:"ContextMenu",Scroll:"ScrollLock",MozPrintableKey:"Unidentified"},eh={8:"Backspace",9:"Tab",12:"Clear",13:"Enter",16:"Shift",17:"Control",18:"Alt",19:"Pause",20:"CapsLock",27:"Escape",32:" ",33:"PageUp",34:"PageDown",35:"End",36:"Home",37:"ArrowLeft",38:"ArrowUp",39:"ArrowRight",40:"ArrowDown",45:"Insert",46:"Delete",112:"F1",113:"F2",114:"F3",115:"F4",116:"F5",117:"F6",118:"F7",119:"F8",120:"F9",121:"F10",122:"F11",123:"F12",144:"NumLock",145:"ScrollLock",224:"Meta"},th={Alt:"altKey",Control:"ctrlKey",Meta:"metaKey",Shift:"shiftKey"};function nh(e){var t=this.nativeEvent;return t.getModifierState?t.getModifierState(e):(e=th[e])?!!t[e]:!1}function Ia(){return nh}var ih=U({},Bi,{key:function(e){if(e.key){var t=Zp[e.key]||e.key;if(t!=="Unidentified")return t}return e.type==="keypress"?(e=_r(e),e===13?"Enter":String.fromCharCode(e)):e.type==="keydown"||e.type==="keyup"?eh[e.keyCode]||"Unidentified":""},code:0,location:0,ctrlKey:0,shiftKey:0,altKey:0,metaKey:0,repeat:0,locale:0,getModifierState:Ia,charCode:function(e){return e.type==="keypress"?_r(e):0},keyCode:function(e){return e.type==="keydown"||e.type==="keyup"?e.keyCode:0},which:function(e){return e.type==="keypress"?_r(e):e.type==="keydown"||e.type==="keyup"?e.keyCode:0}}),rh=Ie(ih),sh=U({},ls,{pointerId:0,width:0,height:0,pressure:0,tangentialPressure:0,tiltX:0,tiltY:0,twist:0,pointerType:0,isPrimary:0}),Hl=Ie(sh),oh=U({},Bi,{touches:0,targetTouches:0,changedTouches:0,altKey:0,metaKey:0,ctrlKey:0,shiftKey:0,getModifierState:Ia}),ah=Ie(oh),lh=U({},Fn,{propertyName:0,elapsedTime:0,pseudoElement:0}),ch=Ie(lh),uh=U({},ls,{deltaX:function(e){return"deltaX"in e?e.deltaX:"wheelDeltaX"in e?-e.wheelDeltaX:0},deltaY:function(e){return"deltaY"in e?e.deltaY:"wheelDeltaY"in e?-e.wheelDeltaY:"wheelDelta"in e?-e.wheelDelta:0},deltaZ:0,deltaMode:0}),fh=Ie(uh),dh=[9,13,27,32],Oa=lt&&"CompositionEvent"in window,ui=null;lt&&"documentMode"in document&&(ui=document.documentMode);var ph=lt&&"TextEvent"in window&&!ui,Pu=lt&&(!Oa||ui&&8<ui&&11>=ui),Vl=" ",Ul=!1;function ju(e,t){switch(e){case"keyup":return dh.indexOf(t.keyCode)!==-1;case"keydown":return t.keyCode!==229;case"keypress":case"mousedown":case"focusout":return!0;default:return!1}}function $u(e){return e=e.detail,typeof e=="object"&&"data"in e?e.data:null}var ln=!1;function hh(e,t){switch(e){case"compositionend":return $u(t);case"keypress":return t.which!==32?null:(Ul=!0,Vl);case"textInput":return e=t.data,e===Vl&&Ul?null:e;default:return null}}function mh(e,t){if(ln)return e==="compositionend"||!Oa&&ju(e,t)?(e=Ru(),Sr=Na=wt=null,ln=!1,e):null;switch(e){case"paste":return null;case"keypress":if(!(t.ctrlKey||t.altKey||t.metaKey)||t.ctrlKey&&t.altKey){if(t.char&&1<t.char.length)return t.char;if(t.which)return String.fromCharCode(t.which)}return null;case"compositionend":return Pu&&t.locale!=="ko"?null:t.data;default:return null}}var gh={color:!0,date:!0,datetime:!0,"datetime-local":!0,email:!0,month:!0,number:!0,password:!0,range:!0,search:!0,tel:!0,text:!0,time:!0,url:!0,week:!0};function Kl(e){var t=e&&e.nodeName&&e.nodeName.toLowerCase();return t==="input"?!!gh[e.type]:t==="textarea"}function Fu(e,t,n,i){gu(i),t=zr(t,"onChange"),0<t.length&&(n=new Ta("onChange","change",null,n,i),e.push({event:n,listeners:t}))}var fi=null,Mi=null;function yh(e){Yu(e,0)}function cs(e){var t=fn(e);if(cu(t))return e}function vh(e,t){if(e==="change")return t}var zu=!1;if(lt){var Us;if(lt){var Ks="oninput"in document;if(!Ks){var Wl=document.createElement("div");Wl.setAttribute("oninput","return;"),Ks=typeof Wl.oninput=="function"}Us=Ks}else Us=!1;zu=Us&&(!document.documentMode||9<document.documentMode)}function ql(){fi&&(fi.detachEvent("onpropertychange",Bu),Mi=fi=null)}function Bu(e){if(e.propertyName==="value"&&cs(Mi)){var t=[];Fu(t,Mi,e,ba(e)),ku(yh,t)}}function wh(e,t,n){e==="focusin"?(ql(),fi=t,Mi=n,fi.attachEvent("onpropertychange",Bu)):e==="focusout"&&ql()}function kh(e){if(e==="selectionchange"||e==="keyup"||e==="keydown")return cs(Mi)}function Sh(e,t){if(e==="click")return cs(t)}function _h(e,t){if(e==="input"||e==="change")return cs(t)}function bh(e,t){return e===t&&(e!==0||1/e===1/t)||e!==e&&t!==t}var qe=typeof Object.is=="function"?Object.is:bh;function Ai(e,t){if(qe(e,t))return!0;if(typeof e!="object"||e===null||typeof t!="object"||t===null)return!1;var n=Object.keys(e),i=Object.keys(t);if(n.length!==i.length)return!1;for(i=0;i<n.length;i++){var r=n[i];if(!ho.call(t,r)||!qe(e[r],t[r]))return!1}return!0}function Ql(e){for(;e&&e.firstChild;)e=e.firstChild;return e}function Gl(e,t){var n=Ql(e);e=0;for(var i;n;){if(n.nodeType===3){if(i=e+n.textContent.length,e<=t&&i>=t)return{node:n,offset:t-e};e=i}e:{for(;n;){if(n.nextSibling){n=n.nextSibling;break e}n=n.parentNode}n=void 0}n=Ql(n)}}function Hu(e,t){return e&&t?e===t?!0:e&&e.nodeType===3?!1:t&&t.nodeType===3?Hu(e,t.parentNode):"contains"in e?e.contains(t):e.compareDocumentPosition?!!(e.compareDocumentPosition(t)&16):!1:!1}function Vu(){for(var e=window,t=Dr();t instanceof e.HTMLIFrameElement;){try{var n=typeof t.contentWindow.location.href=="string"}catch{n=!1}if(n)e=t.contentWindow;else break;t=Dr(e.document)}return t}function La(e){var t=e&&e.nodeName&&e.nodeName.toLowerCase();return t&&(t==="input"&&(e.type==="text"||e.type==="search"||e.type==="tel"||e.type==="url"||e.type==="password")||t==="textarea"||e.contentEditable==="true")}function Eh(e){var t=Vu(),n=e.focusedElem,i=e.selectionRange;if(t!==n&&n&&n.ownerDocument&&Hu(n.ownerDocument.documentElement,n)){if(i!==null&&La(n)){if(t=i.start,e=i.end,e===void 0&&(e=t),"selectionStart"in n)n.selectionStart=t,n.selectionEnd=Math.min(e,n.value.length);else if(e=(t=n.ownerDocument||document)&&t.defaultView||window,e.getSelection){e=e.getSelection();var r=n.textContent.length,s=Math.min(i.start,r);i=i.end===void 0?s:Math.min(i.end,r),!e.extend&&s>i&&(r=i,i=s,s=r),r=Gl(n,s);var o=Gl(n,i);r&&o&&(e.rangeCount!==1||e.anchorNode!==r.node||e.anchorOffset!==r.offset||e.focusNode!==o.node||e.focusOffset!==o.offset)&&(t=t.createRange(),t.setStart(r.node,r.offset),e.removeAllRanges(),s>i?(e.addRange(t),e.extend(o.node,o.offset)):(t.setEnd(o.node,o.offset),e.addRange(t)))}}for(t=[],e=n;e=e.parentNode;)e.nodeType===1&&t.push({element:e,left:e.scrollLeft,top:e.scrollTop});for(typeof n.focus=="function"&&n.focus(),n=0;n<t.length;n++)e=t[n],e.element.scrollLeft=e.left,e.element.scrollTop=e.top}}var Ch=lt&&"documentMode"in document&&11>=document.documentMode,cn=null,Do=null,di=null,xo=!1;function Yl(e,t,n){var i=n.window===n?n.document:n.nodeType===9?n:n.ownerDocument;xo||cn==null||cn!==Dr(i)||(i=cn,"selectionStart"in i&&La(i)?i={start:i.selectionStart,end:i.selectionEnd}:(i=(i.ownerDocument&&i.ownerDocument.defaultView||window).getSelection(),i={anchorNode:i.anchorNode,anchorOffset:i.anchorOffset,focusNode:i.focusNode,focusOffset:i.focusOffset}),di&&Ai(di,i)||(di=i,i=zr(Do,"onSelect"),0<i.length&&(t=new Ta("onSelect","select",null,t,n),e.push({event:t,listeners:i}),t.target=cn)))}function rr(e,t){var n={};return n[e.toLowerCase()]=t.toLowerCase(),n["Webkit"+e]="webkit"+t,n["Moz"+e]="moz"+t,n}var un={animationend:rr("Animation","AnimationEnd"),animationiteration:rr("Animation","AnimationIteration"),animationstart:rr("Animation","AnimationStart"),transitionend:rr("Transition","TransitionEnd")},Ws={},Uu={};lt&&(Uu=document.createElement("div").style,"AnimationEvent"in window||(delete un.animationend.animation,delete un.animationiteration.animation,delete un.animationstart.animation),"TransitionEvent"in window||delete un.transitionend.transition);function us(e){if(Ws[e])return Ws[e];if(!un[e])return e;var t=un[e],n;for(n in t)if(t.hasOwnProperty(n)&&n in Uu)return Ws[e]=t[n];return e}var Ku=us("animationend"),Wu=us("animationiteration"),qu=us("animationstart"),Qu=us("transitionend"),Gu=new Map,Jl="abort auxClick cancel canPlay canPlayThrough click close contextMenu copy cut drag dragEnd dragEnter dragExit dragLeave dragOver dragStart drop durationChange emptied encrypted ended error gotPointerCapture input invalid keyDown keyPress keyUp load loadedData loadedMetadata loadStart lostPointerCapture mouseDown mouseMove mouseOut mouseOver mouseUp paste pause play playing pointerCancel pointerDown pointerMove pointerOut pointerOver pointerUp progress rateChange reset resize seeked seeking stalled submit suspend timeUpdate touchCancel touchEnd touchStart volumeChange scroll toggle touchMove waiting wheel".split(" ");function Lt(e,t){Gu.set(e,t),en(t,[e])}for(var qs=0;qs<Jl.length;qs++){var Qs=Jl[qs],Mh=Qs.toLowerCase(),Ah=Qs[0].toUpperCase()+Qs.slice(1);Lt(Mh,"on"+Ah)}Lt(Ku,"onAnimationEnd");Lt(Wu,"onAnimationIteration");Lt(qu,"onAnimationStart");Lt("dblclick","onDoubleClick");Lt("focusin","onFocus");Lt("focusout","onBlur");Lt(Qu,"onTransitionEnd");Tn("onMouseEnter",["mouseout","mouseover"]);Tn("onMouseLeave",["mouseout","mouseover"]);Tn("onPointerEnter",["pointerout","pointerover"]);Tn("onPointerLeave",["pointerout","pointerover"]);en("onChange","change click focusin focusout input keydown keyup selectionchange".split(" "));en("onSelect","focusout contextmenu dragend focusin keydown keyup mousedown mouseup selectionchange".split(" "));en("onBeforeInput",["compositionend","keypress","textInput","paste"]);en("onCompositionEnd","compositionend focusout keydown keypress keyup mousedown".split(" "));en("onCompositionStart","compositionstart focusout keydown keypress keyup mousedown".split(" "));en("onCompositionUpdate","compositionupdate focusout keydown keypress keyup mousedown".split(" "));var si="abort canplay canplaythrough durationchange emptied encrypted ended error loadeddata loadedmetadata loadstart pause play playing progress ratechange resize seeked seeking stalled suspend timeupdate volumechange waiting".split(" "),Nh=new Set("cancel close invalid load scroll toggle".split(" ").concat(si));function Xl(e,t,n){var i=e.type||"unknown-event";e.currentTarget=n,Mp(i,t,void 0,e),e.currentTarget=null}function Yu(e,t){t=(t&4)!==0;for(var n=0;n<e.length;n++){var i=e[n],r=i.event;i=i.listeners;e:{var s=void 0;if(t)for(var o=i.length-1;0<=o;o--){var a=i[o],l=a.instance,c=a.currentTarget;if(a=a.listener,l!==s&&r.isPropagationStopped())break e;Xl(r,a,c),s=l}else for(o=0;o<i.length;o++){if(a=i[o],l=a.instance,c=a.currentTarget,a=a.listener,l!==s&&r.isPropagationStopped())break e;Xl(r,a,c),s=l}}}if(Rr)throw e=To,Rr=!1,To=null,e}function F(e,t){var n=t[Fo];n===void 0&&(n=t[Fo]=new Set);var i=e+"__bubble";n.has(i)||(Ju(t,e,2,!1),n.add(i))}function Gs(e,t,n){var i=0;t&&(i|=4),Ju(n,e,i,t)}var sr="_reactListening"+Math.random().toString(36).slice(2);function Ni(e){if(!e[sr]){e[sr]=!0,ru.forEach(function(n){n!=="selectionchange"&&(Nh.has(n)||Gs(n,!1,e),Gs(n,!0,e))});var t=e.nodeType===9?e:e.ownerDocument;t===null||t[sr]||(t[sr]=!0,Gs("selectionchange",!1,t))}}function Ju(e,t,n,i){switch(xu(t)){case 1:var r=Hp;break;case 4:r=Vp;break;default:r=Aa}n=r.bind(null,t,n,e),r=void 0,!No||t!=="touchstart"&&t!=="touchmove"&&t!=="wheel"||(r=!0),i?r!==void 0?e.addEventListener(t,n,{capture:!0,passive:r}):e.addEventListener(t,n,!0):r!==void 0?e.addEventListener(t,n,{passive:r}):e.addEventListener(t,n,!1)}function Ys(e,t,n,i,r){var s=i;if(!(t&1)&&!(t&2)&&i!==null)e:for(;;){if(i===null)return;var o=i.tag;if(o===3||o===4){var a=i.stateNode.containerInfo;if(a===r||a.nodeType===8&&a.parentNode===r)break;if(o===4)for(o=i.return;o!==null;){var l=o.tag;if((l===3||l===4)&&(l=o.stateNode.containerInfo,l===r||l.nodeType===8&&l.parentNode===r))return;o=o.return}for(;a!==null;){if(o=zt(a),o===null)return;if(l=o.tag,l===5||l===6){i=s=o;continue e}a=a.parentNode}}i=i.return}ku(function(){var c=s,h=ba(n),u=[];e:{var p=Gu.get(e);if(p!==void 0){var g=Ta,v=e;switch(e){case"keypress":if(_r(n)===0)break e;case"keydown":case"keyup":g=rh;break;case"focusin":v="focus",g=Vs;break;case"focusout":v="blur",g=Vs;break;case"beforeblur":case"afterblur":g=Vs;break;case"click":if(n.button===2)break e;case"auxclick":case"dblclick":case"mousedown":case"mousemove":case"mouseup":case"mouseout":case"mouseover":case"contextmenu":g=zl;break;case"drag":case"dragend":case"dragenter":case"dragexit":case"dragleave":case"dragover":case"dragstart":case"drop":g=Wp;break;case"touchcancel":case"touchend":case"touchmove":case"touchstart":g=ah;break;case Ku:case Wu:case qu:g=Gp;break;case Qu:g=ch;break;case"scroll":g=Up;break;case"wheel":g=fh;break;case"copy":case"cut":case"paste":g=Jp;break;case"gotpointercapture":case"lostpointercapture":case"pointercancel":case"pointerdown":case"pointermove":case"pointerout":case"pointerover":case"pointerup":g=Hl}var y=(t&4)!==0,k=!y&&e==="scroll",d=y?p!==null?p+"Capture":null:p;y=[];for(var f=c,m;f!==null;){m=f;var w=m.stateNode;if(m.tag===5&&w!==null&&(m=w,d!==null&&(w=_i(f,d),w!=null&&y.push(Ti(f,w,m)))),k)break;f=f.return}0<y.length&&(p=new g(p,v,null,n,h),u.push({event:p,listeners:y}))}}if(!(t&7)){e:{if(p=e==="mouseover"||e==="pointerover",g=e==="mouseout"||e==="pointerout",p&&n!==Mo&&(v=n.relatedTarget||n.fromElement)&&(zt(v)||v[ct]))break e;if((g||p)&&(p=h.window===h?h:(p=h.ownerDocument)?p.defaultView||p.parentWindow:window,g?(v=n.relatedTarget||n.toElement,g=c,v=v?zt(v):null,v!==null&&(k=tn(v),v!==k||v.tag!==5&&v.tag!==6)&&(v=null)):(g=null,v=c),g!==v)){if(y=zl,w="onMouseLeave",d="onMouseEnter",f="mouse",(e==="pointerout"||e==="pointerover")&&(y=Hl,w="onPointerLeave",d="onPointerEnter",f="pointer"),k=g==null?p:fn(g),m=v==null?p:fn(v),p=new y(w,f+"leave",g,n,h),p.target=k,p.relatedTarget=m,w=null,zt(h)===c&&(y=new y(d,f+"enter",v,n,h),y.target=m,y.relatedTarget=k,w=y),k=w,g&&v)t:{for(y=g,d=v,f=0,m=y;m;m=nn(m))f++;for(m=0,w=d;w;w=nn(w))m++;for(;0<f-m;)y=nn(y),f--;for(;0<m-f;)d=nn(d),m--;for(;f--;){if(y===d||d!==null&&y===d.alternate)break t;y=nn(y),d=nn(d)}y=null}else y=null;g!==null&&Zl(u,p,g,y,!1),v!==null&&k!==null&&Zl(u,k,v,y,!0)}}e:{if(p=c?fn(c):window,g=p.nodeName&&p.nodeName.toLowerCase(),g==="select"||g==="input"&&p.type==="file")var S=vh;else if(Kl(p))if(zu)S=_h;else{S=kh;var M=wh}else(g=p.nodeName)&&g.toLowerCase()==="input"&&(p.type==="checkbox"||p.type==="radio")&&(S=Sh);if(S&&(S=S(e,c))){Fu(u,S,n,h);break e}M&&M(e,p,c),e==="focusout"&&(M=p._wrapperState)&&M.controlled&&p.type==="number"&&So(p,"number",p.value)}switch(M=c?fn(c):window,e){case"focusin":(Kl(M)||M.contentEditable==="true")&&(cn=M,Do=c,di=null);break;case"focusout":di=Do=cn=null;break;case"mousedown":xo=!0;break;case"contextmenu":case"mouseup":case"dragend":xo=!1,Yl(u,n,h);break;case"selectionchange":if(Ch)break;case"keydown":case"keyup":Yl(u,n,h)}var E;if(Oa)e:{switch(e){case"compositionstart":var _="onCompositionStart";break e;case"compositionend":_="onCompositionEnd";break e;case"compositionupdate":_="onCompositionUpdate";break e}_=void 0}else ln?ju(e,n)&&(_="onCompositionEnd"):e==="keydown"&&n.keyCode===229&&(_="onCompositionStart");_&&(Pu&&n.locale!=="ko"&&(ln||_!=="onCompositionStart"?_==="onCompositionEnd"&&ln&&(E=Ru()):(wt=h,Na="value"in wt?wt.value:wt.textContent,ln=!0)),M=zr(c,_),0<M.length&&(_=new Bl(_,e,null,n,h),u.push({event:_,listeners:M}),E?_.data=E:(E=$u(n),E!==null&&(_.data=E)))),(E=ph?hh(e,n):mh(e,n))&&(c=zr(c,"onBeforeInput"),0<c.length&&(h=new Bl("onBeforeInput","beforeinput",null,n,h),u.push({event:h,listeners:c}),h.data=E))}Yu(u,t)})}function Ti(e,t,n){return{instance:e,listener:t,currentTarget:n}}function zr(e,t){for(var n=t+"Capture",i=[];e!==null;){var r=e,s=r.stateNode;r.tag===5&&s!==null&&(r=s,s=_i(e,n),s!=null&&i.unshift(Ti(e,s,r)),s=_i(e,t),s!=null&&i.push(Ti(e,s,r))),e=e.return}return i}function nn(e){if(e===null)return null;do e=e.return;while(e&&e.tag!==5);return e||null}function Zl(e,t,n,i,r){for(var s=t._reactName,o=[];n!==null&&n!==i;){var a=n,l=a.alternate,c=a.stateNode;if(l!==null&&l===i)break;a.tag===5&&c!==null&&(a=c,r?(l=_i(n,s),l!=null&&o.unshift(Ti(n,l,a))):r||(l=_i(n,s),l!=null&&o.push(Ti(n,l,a)))),n=n.return}o.length!==0&&e.push({event:t,listeners:o})}var Th=/\r\n?/g,Ih=/\u0000|\uFFFD/g;function ec(e){return(typeof e=="string"?e:""+e).replace(Th,`
`).replace(Ih,"")}function or(e,t,n){if(t=ec(t),ec(e)!==t&&n)throw Error(C(425))}function Br(){}var Ro=null,Po=null;function jo(e,t){return e==="textarea"||e==="noscript"||typeof t.children=="string"||typeof t.children=="number"||typeof t.dangerouslySetInnerHTML=="object"&&t.dangerouslySetInnerHTML!==null&&t.dangerouslySetInnerHTML.__html!=null}var $o=typeof setTimeout=="function"?setTimeout:void 0,Oh=typeof clearTimeout=="function"?clearTimeout:void 0,tc=typeof Promise=="function"?Promise:void 0,Lh=typeof queueMicrotask=="function"?queueMicrotask:typeof tc<"u"?function(e){return tc.resolve(null).then(e).catch(Dh)}:$o;function Dh(e){setTimeout(function(){throw e})}function Js(e,t){var n=t,i=0;do{var r=n.nextSibling;if(e.removeChild(n),r&&r.nodeType===8)if(n=r.data,n==="/$"){if(i===0){e.removeChild(r),Ci(t);return}i--}else n!=="$"&&n!=="$?"&&n!=="$!"||i++;n=r}while(n);Ci(t)}function Et(e){for(;e!=null;e=e.nextSibling){var t=e.nodeType;if(t===1||t===3)break;if(t===8){if(t=e.data,t==="$"||t==="$!"||t==="$?")break;if(t==="/$")return null}}return e}function nc(e){e=e.previousSibling;for(var t=0;e;){if(e.nodeType===8){var n=e.data;if(n==="$"||n==="$!"||n==="$?"){if(t===0)return e;t--}else n==="/$"&&t++}e=e.previousSibling}return null}var zn=Math.random().toString(36).slice(2),Je="__reactFiber$"+zn,Ii="__reactProps$"+zn,ct="__reactContainer$"+zn,Fo="__reactEvents$"+zn,xh="__reactListeners$"+zn,Rh="__reactHandles$"+zn;function zt(e){var t=e[Je];if(t)return t;for(var n=e.parentNode;n;){if(t=n[ct]||n[Je]){if(n=t.alternate,t.child!==null||n!==null&&n.child!==null)for(e=nc(e);e!==null;){if(n=e[Je])return n;e=nc(e)}return t}e=n,n=e.parentNode}return null}function Hi(e){return e=e[Je]||e[ct],!e||e.tag!==5&&e.tag!==6&&e.tag!==13&&e.tag!==3?null:e}function fn(e){if(e.tag===5||e.tag===6)return e.stateNode;throw Error(C(33))}function fs(e){return e[Ii]||null}var zo=[],dn=-1;function Dt(e){return{current:e}}function z(e){0>dn||(e.current=zo[dn],zo[dn]=null,dn--)}function j(e,t){dn++,zo[dn]=e.current,e.current=t}var Ot={},pe=Dt(Ot),_e=Dt(!1),Qt=Ot;function In(e,t){var n=e.type.contextTypes;if(!n)return Ot;var i=e.stateNode;if(i&&i.__reactInternalMemoizedUnmaskedChildContext===t)return i.__reactInternalMemoizedMaskedChildContext;var r={},s;for(s in n)r[s]=t[s];return i&&(e=e.stateNode,e.__reactInternalMemoizedUnmaskedChildContext=t,e.__reactInternalMemoizedMaskedChildContext=r),r}function be(e){return e=e.childContextTypes,e!=null}function Hr(){z(_e),z(pe)}function ic(e,t,n){if(pe.current!==Ot)throw Error(C(168));j(pe,t),j(_e,n)}function Xu(e,t,n){var i=e.stateNode;if(t=t.childContextTypes,typeof i.getChildContext!="function")return n;i=i.getChildContext();for(var r in i)if(!(r in t))throw Error(C(108,wp(e)||"Unknown",r));return U({},n,i)}function Vr(e){return e=(e=e.stateNode)&&e.__reactInternalMemoizedMergedChildContext||Ot,Qt=pe.current,j(pe,e),j(_e,_e.current),!0}function rc(e,t,n){var i=e.stateNode;if(!i)throw Error(C(169));n?(e=Xu(e,t,Qt),i.__reactInternalMemoizedMergedChildContext=e,z(_e),z(pe),j(pe,e)):z(_e),j(_e,n)}var nt=null,ds=!1,Xs=!1;function Zu(e){nt===null?nt=[e]:nt.push(e)}function Ph(e){ds=!0,Zu(e)}function xt(){if(!Xs&&nt!==null){Xs=!0;var e=0,t=P;try{var n=nt;for(P=1;e<n.length;e++){var i=n[e];do i=i(!0);while(i!==null)}nt=null,ds=!1}catch(r){throw nt!==null&&(nt=nt.slice(e+1)),Eu(Ea,xt),r}finally{P=t,Xs=!1}}return null}var pn=[],hn=0,Ur=null,Kr=0,Oe=[],Le=0,Gt=null,it=1,rt="";function jt(e,t){pn[hn++]=Kr,pn[hn++]=Ur,Ur=e,Kr=t}function ef(e,t,n){Oe[Le++]=it,Oe[Le++]=rt,Oe[Le++]=Gt,Gt=e;var i=it;e=rt;var r=32-Ke(i)-1;i&=~(1<<r),n+=1;var s=32-Ke(t)+r;if(30<s){var o=r-r%5;s=(i&(1<<o)-1).toString(32),i>>=o,r-=o,it=1<<32-Ke(t)+r|n<<r|i,rt=s+e}else it=1<<s|n<<r|i,rt=e}function Da(e){e.return!==null&&(jt(e,1),ef(e,1,0))}function xa(e){for(;e===Ur;)Ur=pn[--hn],pn[hn]=null,Kr=pn[--hn],pn[hn]=null;for(;e===Gt;)Gt=Oe[--Le],Oe[Le]=null,rt=Oe[--Le],Oe[Le]=null,it=Oe[--Le],Oe[Le]=null}var Ae=null,Me=null,B=!1,Ue=null;function tf(e,t){var n=xe(5,null,null,0);n.elementType="DELETED",n.stateNode=t,n.return=e,t=e.deletions,t===null?(e.deletions=[n],e.flags|=16):t.push(n)}function sc(e,t){switch(e.tag){case 5:var n=e.type;return t=t.nodeType!==1||n.toLowerCase()!==t.nodeName.toLowerCase()?null:t,t!==null?(e.stateNode=t,Ae=e,Me=Et(t.firstChild),!0):!1;case 6:return t=e.pendingProps===""||t.nodeType!==3?null:t,t!==null?(e.stateNode=t,Ae=e,Me=null,!0):!1;case 13:return t=t.nodeType!==8?null:t,t!==null?(n=Gt!==null?{id:it,overflow:rt}:null,e.memoizedState={dehydrated:t,treeContext:n,retryLane:1073741824},n=xe(18,null,null,0),n.stateNode=t,n.return=e,e.child=n,Ae=e,Me=null,!0):!1;default:return!1}}function Bo(e){return(e.mode&1)!==0&&(e.flags&128)===0}function Ho(e){if(B){var t=Me;if(t){var n=t;if(!sc(e,t)){if(Bo(e))throw Error(C(418));t=Et(n.nextSibling);var i=Ae;t&&sc(e,t)?tf(i,n):(e.flags=e.flags&-4097|2,B=!1,Ae=e)}}else{if(Bo(e))throw Error(C(418));e.flags=e.flags&-4097|2,B=!1,Ae=e}}}function oc(e){for(e=e.return;e!==null&&e.tag!==5&&e.tag!==3&&e.tag!==13;)e=e.return;Ae=e}function ar(e){if(e!==Ae)return!1;if(!B)return oc(e),B=!0,!1;var t;if((t=e.tag!==3)&&!(t=e.tag!==5)&&(t=e.type,t=t!=="head"&&t!=="body"&&!jo(e.type,e.memoizedProps)),t&&(t=Me)){if(Bo(e))throw nf(),Error(C(418));for(;t;)tf(e,t),t=Et(t.nextSibling)}if(oc(e),e.tag===13){if(e=e.memoizedState,e=e!==null?e.dehydrated:null,!e)throw Error(C(317));e:{for(e=e.nextSibling,t=0;e;){if(e.nodeType===8){var n=e.data;if(n==="/$"){if(t===0){Me=Et(e.nextSibling);break e}t--}else n!=="$"&&n!=="$!"&&n!=="$?"||t++}e=e.nextSibling}Me=null}}else Me=Ae?Et(e.stateNode.nextSibling):null;return!0}function nf(){for(var e=Me;e;)e=Et(e.nextSibling)}function On(){Me=Ae=null,B=!1}function Ra(e){Ue===null?Ue=[e]:Ue.push(e)}var jh=dt.ReactCurrentBatchConfig;function Xn(e,t,n){if(e=n.ref,e!==null&&typeof e!="function"&&typeof e!="object"){if(n._owner){if(n=n._owner,n){if(n.tag!==1)throw Error(C(309));var i=n.stateNode}if(!i)throw Error(C(147,e));var r=i,s=""+e;return t!==null&&t.ref!==null&&typeof t.ref=="function"&&t.ref._stringRef===s?t.ref:(t=function(o){var a=r.refs;o===null?delete a[s]:a[s]=o},t._stringRef=s,t)}if(typeof e!="string")throw Error(C(284));if(!n._owner)throw Error(C(290,e))}return e}function lr(e,t){throw e=Object.prototype.toString.call(t),Error(C(31,e==="[object Object]"?"object with keys {"+Object.keys(t).join(", ")+"}":e))}function ac(e){var t=e._init;return t(e._payload)}function rf(e){function t(d,f){if(e){var m=d.deletions;m===null?(d.deletions=[f],d.flags|=16):m.push(f)}}function n(d,f){if(!e)return null;for(;f!==null;)t(d,f),f=f.sibling;return null}function i(d,f){for(d=new Map;f!==null;)f.key!==null?d.set(f.key,f):d.set(f.index,f),f=f.sibling;return d}function r(d,f){return d=Nt(d,f),d.index=0,d.sibling=null,d}function s(d,f,m){return d.index=m,e?(m=d.alternate,m!==null?(m=m.index,m<f?(d.flags|=2,f):m):(d.flags|=2,f)):(d.flags|=1048576,f)}function o(d){return e&&d.alternate===null&&(d.flags|=2),d}function a(d,f,m,w){return f===null||f.tag!==6?(f=so(m,d.mode,w),f.return=d,f):(f=r(f,m),f.return=d,f)}function l(d,f,m,w){var S=m.type;return S===an?h(d,f,m.props.children,w,m.key):f!==null&&(f.elementType===S||typeof S=="object"&&S!==null&&S.$$typeof===ht&&ac(S)===f.type)?(w=r(f,m.props),w.ref=Xn(d,f,m),w.return=d,w):(w=Tr(m.type,m.key,m.props,null,d.mode,w),w.ref=Xn(d,f,m),w.return=d,w)}function c(d,f,m,w){return f===null||f.tag!==4||f.stateNode.containerInfo!==m.containerInfo||f.stateNode.implementation!==m.implementation?(f=oo(m,d.mode,w),f.return=d,f):(f=r(f,m.children||[]),f.return=d,f)}function h(d,f,m,w,S){return f===null||f.tag!==7?(f=qt(m,d.mode,w,S),f.return=d,f):(f=r(f,m),f.return=d,f)}function u(d,f,m){if(typeof f=="string"&&f!==""||typeof f=="number")return f=so(""+f,d.mode,m),f.return=d,f;if(typeof f=="object"&&f!==null){switch(f.$$typeof){case Ji:return m=Tr(f.type,f.key,f.props,null,d.mode,m),m.ref=Xn(d,null,f),m.return=d,m;case on:return f=oo(f,d.mode,m),f.return=d,f;case ht:var w=f._init;return u(d,w(f._payload),m)}if(ii(f)||qn(f))return f=qt(f,d.mode,m,null),f.return=d,f;lr(d,f)}return null}function p(d,f,m,w){var S=f!==null?f.key:null;if(typeof m=="string"&&m!==""||typeof m=="number")return S!==null?null:a(d,f,""+m,w);if(typeof m=="object"&&m!==null){switch(m.$$typeof){case Ji:return m.key===S?l(d,f,m,w):null;case on:return m.key===S?c(d,f,m,w):null;case ht:return S=m._init,p(d,f,S(m._payload),w)}if(ii(m)||qn(m))return S!==null?null:h(d,f,m,w,null);lr(d,m)}return null}function g(d,f,m,w,S){if(typeof w=="string"&&w!==""||typeof w=="number")return d=d.get(m)||null,a(f,d,""+w,S);if(typeof w=="object"&&w!==null){switch(w.$$typeof){case Ji:return d=d.get(w.key===null?m:w.key)||null,l(f,d,w,S);case on:return d=d.get(w.key===null?m:w.key)||null,c(f,d,w,S);case ht:var M=w._init;return g(d,f,m,M(w._payload),S)}if(ii(w)||qn(w))return d=d.get(m)||null,h(f,d,w,S,null);lr(f,w)}return null}function v(d,f,m,w){for(var S=null,M=null,E=f,_=f=0,I=null;E!==null&&_<m.length;_++){E.index>_?(I=E,E=null):I=E.sibling;var T=p(d,E,m[_],w);if(T===null){E===null&&(E=I);break}e&&E&&T.alternate===null&&t(d,E),f=s(T,f,_),M===null?S=T:M.sibling=T,M=T,E=I}if(_===m.length)return n(d,E),B&&jt(d,_),S;if(E===null){for(;_<m.length;_++)E=u(d,m[_],w),E!==null&&(f=s(E,f,_),M===null?S=E:M.sibling=E,M=E);return B&&jt(d,_),S}for(E=i(d,E);_<m.length;_++)I=g(E,d,_,m[_],w),I!==null&&(e&&I.alternate!==null&&E.delete(I.key===null?_:I.key),f=s(I,f,_),M===null?S=I:M.sibling=I,M=I);return e&&E.forEach(function(q){return t(d,q)}),B&&jt(d,_),S}function y(d,f,m,w){var S=qn(m);if(typeof S!="function")throw Error(C(150));if(m=S.call(m),m==null)throw Error(C(151));for(var M=S=null,E=f,_=f=0,I=null,T=m.next();E!==null&&!T.done;_++,T=m.next()){E.index>_?(I=E,E=null):I=E.sibling;var q=p(d,E,T.value,w);if(q===null){E===null&&(E=I);break}e&&E&&q.alternate===null&&t(d,E),f=s(q,f,_),M===null?S=q:M.sibling=q,M=q,E=I}if(T.done)return n(d,E),B&&jt(d,_),S;if(E===null){for(;!T.done;_++,T=m.next())T=u(d,T.value,w),T!==null&&(f=s(T,f,_),M===null?S=T:M.sibling=T,M=T);return B&&jt(d,_),S}for(E=i(d,E);!T.done;_++,T=m.next())T=g(E,d,_,T.value,w),T!==null&&(e&&T.alternate!==null&&E.delete(T.key===null?_:T.key),f=s(T,f,_),M===null?S=T:M.sibling=T,M=T);return e&&E.forEach(function(se){return t(d,se)}),B&&jt(d,_),S}function k(d,f,m,w){if(typeof m=="object"&&m!==null&&m.type===an&&m.key===null&&(m=m.props.children),typeof m=="object"&&m!==null){switch(m.$$typeof){case Ji:e:{for(var S=m.key,M=f;M!==null;){if(M.key===S){if(S=m.type,S===an){if(M.tag===7){n(d,M.sibling),f=r(M,m.props.children),f.return=d,d=f;break e}}else if(M.elementType===S||typeof S=="object"&&S!==null&&S.$$typeof===ht&&ac(S)===M.type){n(d,M.sibling),f=r(M,m.props),f.ref=Xn(d,M,m),f.return=d,d=f;break e}n(d,M);break}else t(d,M);M=M.sibling}m.type===an?(f=qt(m.props.children,d.mode,w,m.key),f.return=d,d=f):(w=Tr(m.type,m.key,m.props,null,d.mode,w),w.ref=Xn(d,f,m),w.return=d,d=w)}return o(d);case on:e:{for(M=m.key;f!==null;){if(f.key===M)if(f.tag===4&&f.stateNode.containerInfo===m.containerInfo&&f.stateNode.implementation===m.implementation){n(d,f.sibling),f=r(f,m.children||[]),f.return=d,d=f;break e}else{n(d,f);break}else t(d,f);f=f.sibling}f=oo(m,d.mode,w),f.return=d,d=f}return o(d);case ht:return M=m._init,k(d,f,M(m._payload),w)}if(ii(m))return v(d,f,m,w);if(qn(m))return y(d,f,m,w);lr(d,m)}return typeof m=="string"&&m!==""||typeof m=="number"?(m=""+m,f!==null&&f.tag===6?(n(d,f.sibling),f=r(f,m),f.return=d,d=f):(n(d,f),f=so(m,d.mode,w),f.return=d,d=f),o(d)):n(d,f)}return k}var Ln=rf(!0),sf=rf(!1),Wr=Dt(null),qr=null,mn=null,Pa=null;function ja(){Pa=mn=qr=null}function $a(e){var t=Wr.current;z(Wr),e._currentValue=t}function Vo(e,t,n){for(;e!==null;){var i=e.alternate;if((e.childLanes&t)!==t?(e.childLanes|=t,i!==null&&(i.childLanes|=t)):i!==null&&(i.childLanes&t)!==t&&(i.childLanes|=t),e===n)break;e=e.return}}function Cn(e,t){qr=e,Pa=mn=null,e=e.dependencies,e!==null&&e.firstContext!==null&&(e.lanes&t&&(Se=!0),e.firstContext=null)}function je(e){var t=e._currentValue;if(Pa!==e)if(e={context:e,memoizedValue:t,next:null},mn===null){if(qr===null)throw Error(C(308));mn=e,qr.dependencies={lanes:0,firstContext:e}}else mn=mn.next=e;return t}var Bt=null;function Fa(e){Bt===null?Bt=[e]:Bt.push(e)}function of(e,t,n,i){var r=t.interleaved;return r===null?(n.next=n,Fa(t)):(n.next=r.next,r.next=n),t.interleaved=n,ut(e,i)}function ut(e,t){e.lanes|=t;var n=e.alternate;for(n!==null&&(n.lanes|=t),n=e,e=e.return;e!==null;)e.childLanes|=t,n=e.alternate,n!==null&&(n.childLanes|=t),n=e,e=e.return;return n.tag===3?n.stateNode:null}var mt=!1;function za(e){e.updateQueue={baseState:e.memoizedState,firstBaseUpdate:null,lastBaseUpdate:null,shared:{pending:null,interleaved:null,lanes:0},effects:null}}function af(e,t){e=e.updateQueue,t.updateQueue===e&&(t.updateQueue={baseState:e.baseState,firstBaseUpdate:e.firstBaseUpdate,lastBaseUpdate:e.lastBaseUpdate,shared:e.shared,effects:e.effects})}function ot(e,t){return{eventTime:e,lane:t,tag:0,payload:null,callback:null,next:null}}function Ct(e,t,n){var i=e.updateQueue;if(i===null)return null;if(i=i.shared,R&2){var r=i.pending;return r===null?t.next=t:(t.next=r.next,r.next=t),i.pending=t,ut(e,n)}return r=i.interleaved,r===null?(t.next=t,Fa(i)):(t.next=r.next,r.next=t),i.interleaved=t,ut(e,n)}function br(e,t,n){if(t=t.updateQueue,t!==null&&(t=t.shared,(n&4194240)!==0)){var i=t.lanes;i&=e.pendingLanes,n|=i,t.lanes=n,Ca(e,n)}}function lc(e,t){var n=e.updateQueue,i=e.alternate;if(i!==null&&(i=i.updateQueue,n===i)){var r=null,s=null;if(n=n.firstBaseUpdate,n!==null){do{var o={eventTime:n.eventTime,lane:n.lane,tag:n.tag,payload:n.payload,callback:n.callback,next:null};s===null?r=s=o:s=s.next=o,n=n.next}while(n!==null);s===null?r=s=t:s=s.next=t}else r=s=t;n={baseState:i.baseState,firstBaseUpdate:r,lastBaseUpdate:s,shared:i.shared,effects:i.effects},e.updateQueue=n;return}e=n.lastBaseUpdate,e===null?n.firstBaseUpdate=t:e.next=t,n.lastBaseUpdate=t}function Qr(e,t,n,i){var r=e.updateQueue;mt=!1;var s=r.firstBaseUpdate,o=r.lastBaseUpdate,a=r.shared.pending;if(a!==null){r.shared.pending=null;var l=a,c=l.next;l.next=null,o===null?s=c:o.next=c,o=l;var h=e.alternate;h!==null&&(h=h.updateQueue,a=h.lastBaseUpdate,a!==o&&(a===null?h.firstBaseUpdate=c:a.next=c,h.lastBaseUpdate=l))}if(s!==null){var u=r.baseState;o=0,h=c=l=null,a=s;do{var p=a.lane,g=a.eventTime;if((i&p)===p){h!==null&&(h=h.next={eventTime:g,lane:0,tag:a.tag,payload:a.payload,callback:a.callback,next:null});e:{var v=e,y=a;switch(p=t,g=n,y.tag){case 1:if(v=y.payload,typeof v=="function"){u=v.call(g,u,p);break e}u=v;break e;case 3:v.flags=v.flags&-65537|128;case 0:if(v=y.payload,p=typeof v=="function"?v.call(g,u,p):v,p==null)break e;u=U({},u,p);break e;case 2:mt=!0}}a.callback!==null&&a.lane!==0&&(e.flags|=64,p=r.effects,p===null?r.effects=[a]:p.push(a))}else g={eventTime:g,lane:p,tag:a.tag,payload:a.payload,callback:a.callback,next:null},h===null?(c=h=g,l=u):h=h.next=g,o|=p;if(a=a.next,a===null){if(a=r.shared.pending,a===null)break;p=a,a=p.next,p.next=null,r.lastBaseUpdate=p,r.shared.pending=null}}while(!0);if(h===null&&(l=u),r.baseState=l,r.firstBaseUpdate=c,r.lastBaseUpdate=h,t=r.shared.interleaved,t!==null){r=t;do o|=r.lane,r=r.next;while(r!==t)}else s===null&&(r.shared.lanes=0);Jt|=o,e.lanes=o,e.memoizedState=u}}function cc(e,t,n){if(e=t.effects,t.effects=null,e!==null)for(t=0;t<e.length;t++){var i=e[t],r=i.callback;if(r!==null){if(i.callback=null,i=n,typeof r!="function")throw Error(C(191,r));r.call(i)}}}var Vi={},Ze=Dt(Vi),Oi=Dt(Vi),Li=Dt(Vi);function Ht(e){if(e===Vi)throw Error(C(174));return e}function Ba(e,t){switch(j(Li,t),j(Oi,e),j(Ze,Vi),e=t.nodeType,e){case 9:case 11:t=(t=t.documentElement)?t.namespaceURI:bo(null,"");break;default:e=e===8?t.parentNode:t,t=e.namespaceURI||null,e=e.tagName,t=bo(t,e)}z(Ze),j(Ze,t)}function Dn(){z(Ze),z(Oi),z(Li)}function lf(e){Ht(Li.current);var t=Ht(Ze.current),n=bo(t,e.type);t!==n&&(j(Oi,e),j(Ze,n))}function Ha(e){Oi.current===e&&(z(Ze),z(Oi))}var H=Dt(0);function Gr(e){for(var t=e;t!==null;){if(t.tag===13){var n=t.memoizedState;if(n!==null&&(n=n.dehydrated,n===null||n.data==="$?"||n.data==="$!"))return t}else if(t.tag===19&&t.memoizedProps.revealOrder!==void 0){if(t.flags&128)return t}else if(t.child!==null){t.child.return=t,t=t.child;continue}if(t===e)break;for(;t.sibling===null;){if(t.return===null||t.return===e)return null;t=t.return}t.sibling.return=t.return,t=t.sibling}return null}var Zs=[];function Va(){for(var e=0;e<Zs.length;e++)Zs[e]._workInProgressVersionPrimary=null;Zs.length=0}var Er=dt.ReactCurrentDispatcher,eo=dt.ReactCurrentBatchConfig,Yt=0,V=null,ee=null,ie=null,Yr=!1,pi=!1,Di=0,$h=0;function ue(){throw Error(C(321))}function Ua(e,t){if(t===null)return!1;for(var n=0;n<t.length&&n<e.length;n++)if(!qe(e[n],t[n]))return!1;return!0}function Ka(e,t,n,i,r,s){if(Yt=s,V=t,t.memoizedState=null,t.updateQueue=null,t.lanes=0,Er.current=e===null||e.memoizedState===null?Hh:Vh,e=n(i,r),pi){s=0;do{if(pi=!1,Di=0,25<=s)throw Error(C(301));s+=1,ie=ee=null,t.updateQueue=null,Er.current=Uh,e=n(i,r)}while(pi)}if(Er.current=Jr,t=ee!==null&&ee.next!==null,Yt=0,ie=ee=V=null,Yr=!1,t)throw Error(C(300));return e}function Wa(){var e=Di!==0;return Di=0,e}function Ye(){var e={memoizedState:null,baseState:null,baseQueue:null,queue:null,next:null};return ie===null?V.memoizedState=ie=e:ie=ie.next=e,ie}function $e(){if(ee===null){var e=V.alternate;e=e!==null?e.memoizedState:null}else e=ee.next;var t=ie===null?V.memoizedState:ie.next;if(t!==null)ie=t,ee=e;else{if(e===null)throw Error(C(310));ee=e,e={memoizedState:ee.memoizedState,baseState:ee.baseState,baseQueue:ee.baseQueue,queue:ee.queue,next:null},ie===null?V.memoizedState=ie=e:ie=ie.next=e}return ie}function xi(e,t){return typeof t=="function"?t(e):t}function to(e){var t=$e(),n=t.queue;if(n===null)throw Error(C(311));n.lastRenderedReducer=e;var i=ee,r=i.baseQueue,s=n.pending;if(s!==null){if(r!==null){var o=r.next;r.next=s.next,s.next=o}i.baseQueue=r=s,n.pending=null}if(r!==null){s=r.next,i=i.baseState;var a=o=null,l=null,c=s;do{var h=c.lane;if((Yt&h)===h)l!==null&&(l=l.next={lane:0,action:c.action,hasEagerState:c.hasEagerState,eagerState:c.eagerState,next:null}),i=c.hasEagerState?c.eagerState:e(i,c.action);else{var u={lane:h,action:c.action,hasEagerState:c.hasEagerState,eagerState:c.eagerState,next:null};l===null?(a=l=u,o=i):l=l.next=u,V.lanes|=h,Jt|=h}c=c.next}while(c!==null&&c!==s);l===null?o=i:l.next=a,qe(i,t.memoizedState)||(Se=!0),t.memoizedState=i,t.baseState=o,t.baseQueue=l,n.lastRenderedState=i}if(e=n.interleaved,e!==null){r=e;do s=r.lane,V.lanes|=s,Jt|=s,r=r.next;while(r!==e)}else r===null&&(n.lanes=0);return[t.memoizedState,n.dispatch]}function no(e){var t=$e(),n=t.queue;if(n===null)throw Error(C(311));n.lastRenderedReducer=e;var i=n.dispatch,r=n.pending,s=t.memoizedState;if(r!==null){n.pending=null;var o=r=r.next;do s=e(s,o.action),o=o.next;while(o!==r);qe(s,t.memoizedState)||(Se=!0),t.memoizedState=s,t.baseQueue===null&&(t.baseState=s),n.lastRenderedState=s}return[s,i]}function cf(){}function uf(e,t){var n=V,i=$e(),r=t(),s=!qe(i.memoizedState,r);if(s&&(i.memoizedState=r,Se=!0),i=i.queue,qa(pf.bind(null,n,i,e),[e]),i.getSnapshot!==t||s||ie!==null&&ie.memoizedState.tag&1){if(n.flags|=2048,Ri(9,df.bind(null,n,i,r,t),void 0,null),re===null)throw Error(C(349));Yt&30||ff(n,t,r)}return r}function ff(e,t,n){e.flags|=16384,e={getSnapshot:t,value:n},t=V.updateQueue,t===null?(t={lastEffect:null,stores:null},V.updateQueue=t,t.stores=[e]):(n=t.stores,n===null?t.stores=[e]:n.push(e))}function df(e,t,n,i){t.value=n,t.getSnapshot=i,hf(t)&&mf(e)}function pf(e,t,n){return n(function(){hf(t)&&mf(e)})}function hf(e){var t=e.getSnapshot;e=e.value;try{var n=t();return!qe(e,n)}catch{return!0}}function mf(e){var t=ut(e,1);t!==null&&We(t,e,1,-1)}function uc(e){var t=Ye();return typeof e=="function"&&(e=e()),t.memoizedState=t.baseState=e,e={pending:null,interleaved:null,lanes:0,dispatch:null,lastRenderedReducer:xi,lastRenderedState:e},t.queue=e,e=e.dispatch=Bh.bind(null,V,e),[t.memoizedState,e]}function Ri(e,t,n,i){return e={tag:e,create:t,destroy:n,deps:i,next:null},t=V.updateQueue,t===null?(t={lastEffect:null,stores:null},V.updateQueue=t,t.lastEffect=e.next=e):(n=t.lastEffect,n===null?t.lastEffect=e.next=e:(i=n.next,n.next=e,e.next=i,t.lastEffect=e)),e}function gf(){return $e().memoizedState}function Cr(e,t,n,i){var r=Ye();V.flags|=e,r.memoizedState=Ri(1|t,n,void 0,i===void 0?null:i)}function ps(e,t,n,i){var r=$e();i=i===void 0?null:i;var s=void 0;if(ee!==null){var o=ee.memoizedState;if(s=o.destroy,i!==null&&Ua(i,o.deps)){r.memoizedState=Ri(t,n,s,i);return}}V.flags|=e,r.memoizedState=Ri(1|t,n,s,i)}function fc(e,t){return Cr(8390656,8,e,t)}function qa(e,t){return ps(2048,8,e,t)}function yf(e,t){return ps(4,2,e,t)}function vf(e,t){return ps(4,4,e,t)}function wf(e,t){if(typeof t=="function")return e=e(),t(e),function(){t(null)};if(t!=null)return e=e(),t.current=e,function(){t.current=null}}function kf(e,t,n){return n=n!=null?n.concat([e]):null,ps(4,4,wf.bind(null,t,e),n)}function Qa(){}function Sf(e,t){var n=$e();t=t===void 0?null:t;var i=n.memoizedState;return i!==null&&t!==null&&Ua(t,i[1])?i[0]:(n.memoizedState=[e,t],e)}function _f(e,t){var n=$e();t=t===void 0?null:t;var i=n.memoizedState;return i!==null&&t!==null&&Ua(t,i[1])?i[0]:(e=e(),n.memoizedState=[e,t],e)}function bf(e,t,n){return Yt&21?(qe(n,t)||(n=Au(),V.lanes|=n,Jt|=n,e.baseState=!0),t):(e.baseState&&(e.baseState=!1,Se=!0),e.memoizedState=n)}function Fh(e,t){var n=P;P=n!==0&&4>n?n:4,e(!0);var i=eo.transition;eo.transition={};try{e(!1),t()}finally{P=n,eo.transition=i}}function Ef(){return $e().memoizedState}function zh(e,t,n){var i=At(e);if(n={lane:i,action:n,hasEagerState:!1,eagerState:null,next:null},Cf(e))Mf(t,n);else if(n=of(e,t,n,i),n!==null){var r=ge();We(n,e,i,r),Af(n,t,i)}}function Bh(e,t,n){var i=At(e),r={lane:i,action:n,hasEagerState:!1,eagerState:null,next:null};if(Cf(e))Mf(t,r);else{var s=e.alternate;if(e.lanes===0&&(s===null||s.lanes===0)&&(s=t.lastRenderedReducer,s!==null))try{var o=t.lastRenderedState,a=s(o,n);if(r.hasEagerState=!0,r.eagerState=a,qe(a,o)){var l=t.interleaved;l===null?(r.next=r,Fa(t)):(r.next=l.next,l.next=r),t.interleaved=r;return}}catch{}finally{}n=of(e,t,r,i),n!==null&&(r=ge(),We(n,e,i,r),Af(n,t,i))}}function Cf(e){var t=e.alternate;return e===V||t!==null&&t===V}function Mf(e,t){pi=Yr=!0;var n=e.pending;n===null?t.next=t:(t.next=n.next,n.next=t),e.pending=t}function Af(e,t,n){if(n&4194240){var i=t.lanes;i&=e.pendingLanes,n|=i,t.lanes=n,Ca(e,n)}}var Jr={readContext:je,useCallback:ue,useContext:ue,useEffect:ue,useImperativeHandle:ue,useInsertionEffect:ue,useLayoutEffect:ue,useMemo:ue,useReducer:ue,useRef:ue,useState:ue,useDebugValue:ue,useDeferredValue:ue,useTransition:ue,useMutableSource:ue,useSyncExternalStore:ue,useId:ue,unstable_isNewReconciler:!1},Hh={readContext:je,useCallback:function(e,t){return Ye().memoizedState=[e,t===void 0?null:t],e},useContext:je,useEffect:fc,useImperativeHandle:function(e,t,n){return n=n!=null?n.concat([e]):null,Cr(4194308,4,wf.bind(null,t,e),n)},useLayoutEffect:function(e,t){return Cr(4194308,4,e,t)},useInsertionEffect:function(e,t){return Cr(4,2,e,t)},useMemo:function(e,t){var n=Ye();return t=t===void 0?null:t,e=e(),n.memoizedState=[e,t],e},useReducer:function(e,t,n){var i=Ye();return t=n!==void 0?n(t):t,i.memoizedState=i.baseState=t,e={pending:null,interleaved:null,lanes:0,dispatch:null,lastRenderedReducer:e,lastRenderedState:t},i.queue=e,e=e.dispatch=zh.bind(null,V,e),[i.memoizedState,e]},useRef:function(e){var t=Ye();return e={current:e},t.memoizedState=e},useState:uc,useDebugValue:Qa,useDeferredValue:function(e){return Ye().memoizedState=e},useTransition:function(){var e=uc(!1),t=e[0];return e=Fh.bind(null,e[1]),Ye().memoizedState=e,[t,e]},useMutableSource:function(){},useSyncExternalStore:function(e,t,n){var i=V,r=Ye();if(B){if(n===void 0)throw Error(C(407));n=n()}else{if(n=t(),re===null)throw Error(C(349));Yt&30||ff(i,t,n)}r.memoizedState=n;var s={value:n,getSnapshot:t};return r.queue=s,fc(pf.bind(null,i,s,e),[e]),i.flags|=2048,Ri(9,df.bind(null,i,s,n,t),void 0,null),n},useId:function(){var e=Ye(),t=re.identifierPrefix;if(B){var n=rt,i=it;n=(i&~(1<<32-Ke(i)-1)).toString(32)+n,t=":"+t+"R"+n,n=Di++,0<n&&(t+="H"+n.toString(32)),t+=":"}else n=$h++,t=":"+t+"r"+n.toString(32)+":";return e.memoizedState=t},unstable_isNewReconciler:!1},Vh={readContext:je,useCallback:Sf,useContext:je,useEffect:qa,useImperativeHandle:kf,useInsertionEffect:yf,useLayoutEffect:vf,useMemo:_f,useReducer:to,useRef:gf,useState:function(){return to(xi)},useDebugValue:Qa,useDeferredValue:function(e){var t=$e();return bf(t,ee.memoizedState,e)},useTransition:function(){var e=to(xi)[0],t=$e().memoizedState;return[e,t]},useMutableSource:cf,useSyncExternalStore:uf,useId:Ef,unstable_isNewReconciler:!1},Uh={readContext:je,useCallback:Sf,useContext:je,useEffect:qa,useImperativeHandle:kf,useInsertionEffect:yf,useLayoutEffect:vf,useMemo:_f,useReducer:no,useRef:gf,useState:function(){return no(xi)},useDebugValue:Qa,useDeferredValue:function(e){var t=$e();return ee===null?t.memoizedState=e:bf(t,ee.memoizedState,e)},useTransition:function(){var e=no(xi)[0],t=$e().memoizedState;return[e,t]},useMutableSource:cf,useSyncExternalStore:uf,useId:Ef,unstable_isNewReconciler:!1};function He(e,t){if(e&&e.defaultProps){t=U({},t),e=e.defaultProps;for(var n in e)t[n]===void 0&&(t[n]=e[n]);return t}return t}function Uo(e,t,n,i){t=e.memoizedState,n=n(i,t),n=n==null?t:U({},t,n),e.memoizedState=n,e.lanes===0&&(e.updateQueue.baseState=n)}var hs={isMounted:function(e){return(e=e._reactInternals)?tn(e)===e:!1},enqueueSetState:function(e,t,n){e=e._reactInternals;var i=ge(),r=At(e),s=ot(i,r);s.payload=t,n!=null&&(s.callback=n),t=Ct(e,s,r),t!==null&&(We(t,e,r,i),br(t,e,r))},enqueueReplaceState:function(e,t,n){e=e._reactInternals;var i=ge(),r=At(e),s=ot(i,r);s.tag=1,s.payload=t,n!=null&&(s.callback=n),t=Ct(e,s,r),t!==null&&(We(t,e,r,i),br(t,e,r))},enqueueForceUpdate:function(e,t){e=e._reactInternals;var n=ge(),i=At(e),r=ot(n,i);r.tag=2,t!=null&&(r.callback=t),t=Ct(e,r,i),t!==null&&(We(t,e,i,n),br(t,e,i))}};function dc(e,t,n,i,r,s,o){return e=e.stateNode,typeof e.shouldComponentUpdate=="function"?e.shouldComponentUpdate(i,s,o):t.prototype&&t.prototype.isPureReactComponent?!Ai(n,i)||!Ai(r,s):!0}function Nf(e,t,n){var i=!1,r=Ot,s=t.contextType;return typeof s=="object"&&s!==null?s=je(s):(r=be(t)?Qt:pe.current,i=t.contextTypes,s=(i=i!=null)?In(e,r):Ot),t=new t(n,s),e.memoizedState=t.state!==null&&t.state!==void 0?t.state:null,t.updater=hs,e.stateNode=t,t._reactInternals=e,i&&(e=e.stateNode,e.__reactInternalMemoizedUnmaskedChildContext=r,e.__reactInternalMemoizedMaskedChildContext=s),t}function pc(e,t,n,i){e=t.state,typeof t.componentWillReceiveProps=="function"&&t.componentWillReceiveProps(n,i),typeof t.UNSAFE_componentWillReceiveProps=="function"&&t.UNSAFE_componentWillReceiveProps(n,i),t.state!==e&&hs.enqueueReplaceState(t,t.state,null)}function Ko(e,t,n,i){var r=e.stateNode;r.props=n,r.state=e.memoizedState,r.refs={},za(e);var s=t.contextType;typeof s=="object"&&s!==null?r.context=je(s):(s=be(t)?Qt:pe.current,r.context=In(e,s)),r.state=e.memoizedState,s=t.getDerivedStateFromProps,typeof s=="function"&&(Uo(e,t,s,n),r.state=e.memoizedState),typeof t.getDerivedStateFromProps=="function"||typeof r.getSnapshotBeforeUpdate=="function"||typeof r.UNSAFE_componentWillMount!="function"&&typeof r.componentWillMount!="function"||(t=r.state,typeof r.componentWillMount=="function"&&r.componentWillMount(),typeof r.UNSAFE_componentWillMount=="function"&&r.UNSAFE_componentWillMount(),t!==r.state&&hs.enqueueReplaceState(r,r.state,null),Qr(e,n,r,i),r.state=e.memoizedState),typeof r.componentDidMount=="function"&&(e.flags|=4194308)}function xn(e,t){try{var n="",i=t;do n+=vp(i),i=i.return;while(i);var r=n}catch(s){r=`
Error generating stack: `+s.message+`
`+s.stack}return{value:e,source:t,stack:r,digest:null}}function io(e,t,n){return{value:e,source:null,stack:n??null,digest:t??null}}function Wo(e,t){try{console.error(t.value)}catch(n){setTimeout(function(){throw n})}}var Kh=typeof WeakMap=="function"?WeakMap:Map;function Tf(e,t,n){n=ot(-1,n),n.tag=3,n.payload={element:null};var i=t.value;return n.callback=function(){Zr||(Zr=!0,na=i),Wo(e,t)},n}function If(e,t,n){n=ot(-1,n),n.tag=3;var i=e.type.getDerivedStateFromError;if(typeof i=="function"){var r=t.value;n.payload=function(){return i(r)},n.callback=function(){Wo(e,t)}}var s=e.stateNode;return s!==null&&typeof s.componentDidCatch=="function"&&(n.callback=function(){Wo(e,t),typeof i!="function"&&(Mt===null?Mt=new Set([this]):Mt.add(this));var o=t.stack;this.componentDidCatch(t.value,{componentStack:o!==null?o:""})}),n}function hc(e,t,n){var i=e.pingCache;if(i===null){i=e.pingCache=new Kh;var r=new Set;i.set(t,r)}else r=i.get(t),r===void 0&&(r=new Set,i.set(t,r));r.has(n)||(r.add(n),e=sm.bind(null,e,t,n),t.then(e,e))}function mc(e){do{var t;if((t=e.tag===13)&&(t=e.memoizedState,t=t!==null?t.dehydrated!==null:!0),t)return e;e=e.return}while(e!==null);return null}function gc(e,t,n,i,r){return e.mode&1?(e.flags|=65536,e.lanes=r,e):(e===t?e.flags|=65536:(e.flags|=128,n.flags|=131072,n.flags&=-52805,n.tag===1&&(n.alternate===null?n.tag=17:(t=ot(-1,1),t.tag=2,Ct(n,t,1))),n.lanes|=1),e)}var Wh=dt.ReactCurrentOwner,Se=!1;function he(e,t,n,i){t.child=e===null?sf(t,null,n,i):Ln(t,e.child,n,i)}function yc(e,t,n,i,r){n=n.render;var s=t.ref;return Cn(t,r),i=Ka(e,t,n,i,s,r),n=Wa(),e!==null&&!Se?(t.updateQueue=e.updateQueue,t.flags&=-2053,e.lanes&=~r,ft(e,t,r)):(B&&n&&Da(t),t.flags|=1,he(e,t,i,r),t.child)}function vc(e,t,n,i,r){if(e===null){var s=n.type;return typeof s=="function"&&!nl(s)&&s.defaultProps===void 0&&n.compare===null&&n.defaultProps===void 0?(t.tag=15,t.type=s,Of(e,t,s,i,r)):(e=Tr(n.type,null,i,t,t.mode,r),e.ref=t.ref,e.return=t,t.child=e)}if(s=e.child,!(e.lanes&r)){var o=s.memoizedProps;if(n=n.compare,n=n!==null?n:Ai,n(o,i)&&e.ref===t.ref)return ft(e,t,r)}return t.flags|=1,e=Nt(s,i),e.ref=t.ref,e.return=t,t.child=e}function Of(e,t,n,i,r){if(e!==null){var s=e.memoizedProps;if(Ai(s,i)&&e.ref===t.ref)if(Se=!1,t.pendingProps=i=s,(e.lanes&r)!==0)e.flags&131072&&(Se=!0);else return t.lanes=e.lanes,ft(e,t,r)}return qo(e,t,n,i,r)}function Lf(e,t,n){var i=t.pendingProps,r=i.children,s=e!==null?e.memoizedState:null;if(i.mode==="hidden")if(!(t.mode&1))t.memoizedState={baseLanes:0,cachePool:null,transitions:null},j(yn,Ce),Ce|=n;else{if(!(n&1073741824))return e=s!==null?s.baseLanes|n:n,t.lanes=t.childLanes=1073741824,t.memoizedState={baseLanes:e,cachePool:null,transitions:null},t.updateQueue=null,j(yn,Ce),Ce|=e,null;t.memoizedState={baseLanes:0,cachePool:null,transitions:null},i=s!==null?s.baseLanes:n,j(yn,Ce),Ce|=i}else s!==null?(i=s.baseLanes|n,t.memoizedState=null):i=n,j(yn,Ce),Ce|=i;return he(e,t,r,n),t.child}function Df(e,t){var n=t.ref;(e===null&&n!==null||e!==null&&e.ref!==n)&&(t.flags|=512,t.flags|=2097152)}function qo(e,t,n,i,r){var s=be(n)?Qt:pe.current;return s=In(t,s),Cn(t,r),n=Ka(e,t,n,i,s,r),i=Wa(),e!==null&&!Se?(t.updateQueue=e.updateQueue,t.flags&=-2053,e.lanes&=~r,ft(e,t,r)):(B&&i&&Da(t),t.flags|=1,he(e,t,n,r),t.child)}function wc(e,t,n,i,r){if(be(n)){var s=!0;Vr(t)}else s=!1;if(Cn(t,r),t.stateNode===null)Mr(e,t),Nf(t,n,i),Ko(t,n,i,r),i=!0;else if(e===null){var o=t.stateNode,a=t.memoizedProps;o.props=a;var l=o.context,c=n.contextType;typeof c=="object"&&c!==null?c=je(c):(c=be(n)?Qt:pe.current,c=In(t,c));var h=n.getDerivedStateFromProps,u=typeof h=="function"||typeof o.getSnapshotBeforeUpdate=="function";u||typeof o.UNSAFE_componentWillReceiveProps!="function"&&typeof o.componentWillReceiveProps!="function"||(a!==i||l!==c)&&pc(t,o,i,c),mt=!1;var p=t.memoizedState;o.state=p,Qr(t,i,o,r),l=t.memoizedState,a!==i||p!==l||_e.current||mt?(typeof h=="function"&&(Uo(t,n,h,i),l=t.memoizedState),(a=mt||dc(t,n,a,i,p,l,c))?(u||typeof o.UNSAFE_componentWillMount!="function"&&typeof o.componentWillMount!="function"||(typeof o.componentWillMount=="function"&&o.componentWillMount(),typeof o.UNSAFE_componentWillMount=="function"&&o.UNSAFE_componentWillMount()),typeof o.componentDidMount=="function"&&(t.flags|=4194308)):(typeof o.componentDidMount=="function"&&(t.flags|=4194308),t.memoizedProps=i,t.memoizedState=l),o.props=i,o.state=l,o.context=c,i=a):(typeof o.componentDidMount=="function"&&(t.flags|=4194308),i=!1)}else{o=t.stateNode,af(e,t),a=t.memoizedProps,c=t.type===t.elementType?a:He(t.type,a),o.props=c,u=t.pendingProps,p=o.context,l=n.contextType,typeof l=="object"&&l!==null?l=je(l):(l=be(n)?Qt:pe.current,l=In(t,l));var g=n.getDerivedStateFromProps;(h=typeof g=="function"||typeof o.getSnapshotBeforeUpdate=="function")||typeof o.UNSAFE_componentWillReceiveProps!="function"&&typeof o.componentWillReceiveProps!="function"||(a!==u||p!==l)&&pc(t,o,i,l),mt=!1,p=t.memoizedState,o.state=p,Qr(t,i,o,r);var v=t.memoizedState;a!==u||p!==v||_e.current||mt?(typeof g=="function"&&(Uo(t,n,g,i),v=t.memoizedState),(c=mt||dc(t,n,c,i,p,v,l)||!1)?(h||typeof o.UNSAFE_componentWillUpdate!="function"&&typeof o.componentWillUpdate!="function"||(typeof o.componentWillUpdate=="function"&&o.componentWillUpdate(i,v,l),typeof o.UNSAFE_componentWillUpdate=="function"&&o.UNSAFE_componentWillUpdate(i,v,l)),typeof o.componentDidUpdate=="function"&&(t.flags|=4),typeof o.getSnapshotBeforeUpdate=="function"&&(t.flags|=1024)):(typeof o.componentDidUpdate!="function"||a===e.memoizedProps&&p===e.memoizedState||(t.flags|=4),typeof o.getSnapshotBeforeUpdate!="function"||a===e.memoizedProps&&p===e.memoizedState||(t.flags|=1024),t.memoizedProps=i,t.memoizedState=v),o.props=i,o.state=v,o.context=l,i=c):(typeof o.componentDidUpdate!="function"||a===e.memoizedProps&&p===e.memoizedState||(t.flags|=4),typeof o.getSnapshotBeforeUpdate!="function"||a===e.memoizedProps&&p===e.memoizedState||(t.flags|=1024),i=!1)}return Qo(e,t,n,i,s,r)}function Qo(e,t,n,i,r,s){Df(e,t);var o=(t.flags&128)!==0;if(!i&&!o)return r&&rc(t,n,!1),ft(e,t,s);i=t.stateNode,Wh.current=t;var a=o&&typeof n.getDerivedStateFromError!="function"?null:i.render();return t.flags|=1,e!==null&&o?(t.child=Ln(t,e.child,null,s),t.child=Ln(t,null,a,s)):he(e,t,a,s),t.memoizedState=i.state,r&&rc(t,n,!0),t.child}function xf(e){var t=e.stateNode;t.pendingContext?ic(e,t.pendingContext,t.pendingContext!==t.context):t.context&&ic(e,t.context,!1),Ba(e,t.containerInfo)}function kc(e,t,n,i,r){return On(),Ra(r),t.flags|=256,he(e,t,n,i),t.child}var Go={dehydrated:null,treeContext:null,retryLane:0};function Yo(e){return{baseLanes:e,cachePool:null,transitions:null}}function Rf(e,t,n){var i=t.pendingProps,r=H.current,s=!1,o=(t.flags&128)!==0,a;if((a=o)||(a=e!==null&&e.memoizedState===null?!1:(r&2)!==0),a?(s=!0,t.flags&=-129):(e===null||e.memoizedState!==null)&&(r|=1),j(H,r&1),e===null)return Ho(t),e=t.memoizedState,e!==null&&(e=e.dehydrated,e!==null)?(t.mode&1?e.data==="$!"?t.lanes=8:t.lanes=1073741824:t.lanes=1,null):(o=i.children,e=i.fallback,s?(i=t.mode,s=t.child,o={mode:"hidden",children:o},!(i&1)&&s!==null?(s.childLanes=0,s.pendingProps=o):s=ys(o,i,0,null),e=qt(e,i,n,null),s.return=t,e.return=t,s.sibling=e,t.child=s,t.child.memoizedState=Yo(n),t.memoizedState=Go,e):Ga(t,o));if(r=e.memoizedState,r!==null&&(a=r.dehydrated,a!==null))return qh(e,t,o,i,a,r,n);if(s){s=i.fallback,o=t.mode,r=e.child,a=r.sibling;var l={mode:"hidden",children:i.children};return!(o&1)&&t.child!==r?(i=t.child,i.childLanes=0,i.pendingProps=l,t.deletions=null):(i=Nt(r,l),i.subtreeFlags=r.subtreeFlags&14680064),a!==null?s=Nt(a,s):(s=qt(s,o,n,null),s.flags|=2),s.return=t,i.return=t,i.sibling=s,t.child=i,i=s,s=t.child,o=e.child.memoizedState,o=o===null?Yo(n):{baseLanes:o.baseLanes|n,cachePool:null,transitions:o.transitions},s.memoizedState=o,s.childLanes=e.childLanes&~n,t.memoizedState=Go,i}return s=e.child,e=s.sibling,i=Nt(s,{mode:"visible",children:i.children}),!(t.mode&1)&&(i.lanes=n),i.return=t,i.sibling=null,e!==null&&(n=t.deletions,n===null?(t.deletions=[e],t.flags|=16):n.push(e)),t.child=i,t.memoizedState=null,i}function Ga(e,t){return t=ys({mode:"visible",children:t},e.mode,0,null),t.return=e,e.child=t}function cr(e,t,n,i){return i!==null&&Ra(i),Ln(t,e.child,null,n),e=Ga(t,t.pendingProps.children),e.flags|=2,t.memoizedState=null,e}function qh(e,t,n,i,r,s,o){if(n)return t.flags&256?(t.flags&=-257,i=io(Error(C(422))),cr(e,t,o,i)):t.memoizedState!==null?(t.child=e.child,t.flags|=128,null):(s=i.fallback,r=t.mode,i=ys({mode:"visible",children:i.children},r,0,null),s=qt(s,r,o,null),s.flags|=2,i.return=t,s.return=t,i.sibling=s,t.child=i,t.mode&1&&Ln(t,e.child,null,o),t.child.memoizedState=Yo(o),t.memoizedState=Go,s);if(!(t.mode&1))return cr(e,t,o,null);if(r.data==="$!"){if(i=r.nextSibling&&r.nextSibling.dataset,i)var a=i.dgst;return i=a,s=Error(C(419)),i=io(s,i,void 0),cr(e,t,o,i)}if(a=(o&e.childLanes)!==0,Se||a){if(i=re,i!==null){switch(o&-o){case 4:r=2;break;case 16:r=8;break;case 64:case 128:case 256:case 512:case 1024:case 2048:case 4096:case 8192:case 16384:case 32768:case 65536:case 131072:case 262144:case 524288:case 1048576:case 2097152:case 4194304:case 8388608:case 16777216:case 33554432:case 67108864:r=32;break;case 536870912:r=268435456;break;default:r=0}r=r&(i.suspendedLanes|o)?0:r,r!==0&&r!==s.retryLane&&(s.retryLane=r,ut(e,r),We(i,e,r,-1))}return tl(),i=io(Error(C(421))),cr(e,t,o,i)}return r.data==="$?"?(t.flags|=128,t.child=e.child,t=om.bind(null,e),r._reactRetry=t,null):(e=s.treeContext,Me=Et(r.nextSibling),Ae=t,B=!0,Ue=null,e!==null&&(Oe[Le++]=it,Oe[Le++]=rt,Oe[Le++]=Gt,it=e.id,rt=e.overflow,Gt=t),t=Ga(t,i.children),t.flags|=4096,t)}function Sc(e,t,n){e.lanes|=t;var i=e.alternate;i!==null&&(i.lanes|=t),Vo(e.return,t,n)}function ro(e,t,n,i,r){var s=e.memoizedState;s===null?e.memoizedState={isBackwards:t,rendering:null,renderingStartTime:0,last:i,tail:n,tailMode:r}:(s.isBackwards=t,s.rendering=null,s.renderingStartTime=0,s.last=i,s.tail=n,s.tailMode=r)}function Pf(e,t,n){var i=t.pendingProps,r=i.revealOrder,s=i.tail;if(he(e,t,i.children,n),i=H.current,i&2)i=i&1|2,t.flags|=128;else{if(e!==null&&e.flags&128)e:for(e=t.child;e!==null;){if(e.tag===13)e.memoizedState!==null&&Sc(e,n,t);else if(e.tag===19)Sc(e,n,t);else if(e.child!==null){e.child.return=e,e=e.child;continue}if(e===t)break e;for(;e.sibling===null;){if(e.return===null||e.return===t)break e;e=e.return}e.sibling.return=e.return,e=e.sibling}i&=1}if(j(H,i),!(t.mode&1))t.memoizedState=null;else switch(r){case"forwards":for(n=t.child,r=null;n!==null;)e=n.alternate,e!==null&&Gr(e)===null&&(r=n),n=n.sibling;n=r,n===null?(r=t.child,t.child=null):(r=n.sibling,n.sibling=null),ro(t,!1,r,n,s);break;case"backwards":for(n=null,r=t.child,t.child=null;r!==null;){if(e=r.alternate,e!==null&&Gr(e)===null){t.child=r;break}e=r.sibling,r.sibling=n,n=r,r=e}ro(t,!0,n,null,s);break;case"together":ro(t,!1,null,null,void 0);break;default:t.memoizedState=null}return t.child}function Mr(e,t){!(t.mode&1)&&e!==null&&(e.alternate=null,t.alternate=null,t.flags|=2)}function ft(e,t,n){if(e!==null&&(t.dependencies=e.dependencies),Jt|=t.lanes,!(n&t.childLanes))return null;if(e!==null&&t.child!==e.child)throw Error(C(153));if(t.child!==null){for(e=t.child,n=Nt(e,e.pendingProps),t.child=n,n.return=t;e.sibling!==null;)e=e.sibling,n=n.sibling=Nt(e,e.pendingProps),n.return=t;n.sibling=null}return t.child}function Qh(e,t,n){switch(t.tag){case 3:xf(t),On();break;case 5:lf(t);break;case 1:be(t.type)&&Vr(t);break;case 4:Ba(t,t.stateNode.containerInfo);break;case 10:var i=t.type._context,r=t.memoizedProps.value;j(Wr,i._currentValue),i._currentValue=r;break;case 13:if(i=t.memoizedState,i!==null)return i.dehydrated!==null?(j(H,H.current&1),t.flags|=128,null):n&t.child.childLanes?Rf(e,t,n):(j(H,H.current&1),e=ft(e,t,n),e!==null?e.sibling:null);j(H,H.current&1);break;case 19:if(i=(n&t.childLanes)!==0,e.flags&128){if(i)return Pf(e,t,n);t.flags|=128}if(r=t.memoizedState,r!==null&&(r.rendering=null,r.tail=null,r.lastEffect=null),j(H,H.current),i)break;return null;case 22:case 23:return t.lanes=0,Lf(e,t,n)}return ft(e,t,n)}var jf,Jo,$f,Ff;jf=function(e,t){for(var n=t.child;n!==null;){if(n.tag===5||n.tag===6)e.appendChild(n.stateNode);else if(n.tag!==4&&n.child!==null){n.child.return=n,n=n.child;continue}if(n===t)break;for(;n.sibling===null;){if(n.return===null||n.return===t)return;n=n.return}n.sibling.return=n.return,n=n.sibling}};Jo=function(){};$f=function(e,t,n,i){var r=e.memoizedProps;if(r!==i){e=t.stateNode,Ht(Ze.current);var s=null;switch(n){case"input":r=wo(e,r),i=wo(e,i),s=[];break;case"select":r=U({},r,{value:void 0}),i=U({},i,{value:void 0}),s=[];break;case"textarea":r=_o(e,r),i=_o(e,i),s=[];break;default:typeof r.onClick!="function"&&typeof i.onClick=="function"&&(e.onclick=Br)}Eo(n,i);var o;n=null;for(c in r)if(!i.hasOwnProperty(c)&&r.hasOwnProperty(c)&&r[c]!=null)if(c==="style"){var a=r[c];for(o in a)a.hasOwnProperty(o)&&(n||(n={}),n[o]="")}else c!=="dangerouslySetInnerHTML"&&c!=="children"&&c!=="suppressContentEditableWarning"&&c!=="suppressHydrationWarning"&&c!=="autoFocus"&&(ki.hasOwnProperty(c)?s||(s=[]):(s=s||[]).push(c,null));for(c in i){var l=i[c];if(a=r!=null?r[c]:void 0,i.hasOwnProperty(c)&&l!==a&&(l!=null||a!=null))if(c==="style")if(a){for(o in a)!a.hasOwnProperty(o)||l&&l.hasOwnProperty(o)||(n||(n={}),n[o]="");for(o in l)l.hasOwnProperty(o)&&a[o]!==l[o]&&(n||(n={}),n[o]=l[o])}else n||(s||(s=[]),s.push(c,n)),n=l;else c==="dangerouslySetInnerHTML"?(l=l?l.__html:void 0,a=a?a.__html:void 0,l!=null&&a!==l&&(s=s||[]).push(c,l)):c==="children"?typeof l!="string"&&typeof l!="number"||(s=s||[]).push(c,""+l):c!=="suppressContentEditableWarning"&&c!=="suppressHydrationWarning"&&(ki.hasOwnProperty(c)?(l!=null&&c==="onScroll"&&F("scroll",e),s||a===l||(s=[])):(s=s||[]).push(c,l))}n&&(s=s||[]).push("style",n);var c=s;(t.updateQueue=c)&&(t.flags|=4)}};Ff=function(e,t,n,i){n!==i&&(t.flags|=4)};function Zn(e,t){if(!B)switch(e.tailMode){case"hidden":t=e.tail;for(var n=null;t!==null;)t.alternate!==null&&(n=t),t=t.sibling;n===null?e.tail=null:n.sibling=null;break;case"collapsed":n=e.tail;for(var i=null;n!==null;)n.alternate!==null&&(i=n),n=n.sibling;i===null?t||e.tail===null?e.tail=null:e.tail.sibling=null:i.sibling=null}}function fe(e){var t=e.alternate!==null&&e.alternate.child===e.child,n=0,i=0;if(t)for(var r=e.child;r!==null;)n|=r.lanes|r.childLanes,i|=r.subtreeFlags&14680064,i|=r.flags&14680064,r.return=e,r=r.sibling;else for(r=e.child;r!==null;)n|=r.lanes|r.childLanes,i|=r.subtreeFlags,i|=r.flags,r.return=e,r=r.sibling;return e.subtreeFlags|=i,e.childLanes=n,t}function Gh(e,t,n){var i=t.pendingProps;switch(xa(t),t.tag){case 2:case 16:case 15:case 0:case 11:case 7:case 8:case 12:case 9:case 14:return fe(t),null;case 1:return be(t.type)&&Hr(),fe(t),null;case 3:return i=t.stateNode,Dn(),z(_e),z(pe),Va(),i.pendingContext&&(i.context=i.pendingContext,i.pendingContext=null),(e===null||e.child===null)&&(ar(t)?t.flags|=4:e===null||e.memoizedState.isDehydrated&&!(t.flags&256)||(t.flags|=1024,Ue!==null&&(sa(Ue),Ue=null))),Jo(e,t),fe(t),null;case 5:Ha(t);var r=Ht(Li.current);if(n=t.type,e!==null&&t.stateNode!=null)$f(e,t,n,i,r),e.ref!==t.ref&&(t.flags|=512,t.flags|=2097152);else{if(!i){if(t.stateNode===null)throw Error(C(166));return fe(t),null}if(e=Ht(Ze.current),ar(t)){i=t.stateNode,n=t.type;var s=t.memoizedProps;switch(i[Je]=t,i[Ii]=s,e=(t.mode&1)!==0,n){case"dialog":F("cancel",i),F("close",i);break;case"iframe":case"object":case"embed":F("load",i);break;case"video":case"audio":for(r=0;r<si.length;r++)F(si[r],i);break;case"source":F("error",i);break;case"img":case"image":case"link":F("error",i),F("load",i);break;case"details":F("toggle",i);break;case"input":Il(i,s),F("invalid",i);break;case"select":i._wrapperState={wasMultiple:!!s.multiple},F("invalid",i);break;case"textarea":Ll(i,s),F("invalid",i)}Eo(n,s),r=null;for(var o in s)if(s.hasOwnProperty(o)){var a=s[o];o==="children"?typeof a=="string"?i.textContent!==a&&(s.suppressHydrationWarning!==!0&&or(i.textContent,a,e),r=["children",a]):typeof a=="number"&&i.textContent!==""+a&&(s.suppressHydrationWarning!==!0&&or(i.textContent,a,e),r=["children",""+a]):ki.hasOwnProperty(o)&&a!=null&&o==="onScroll"&&F("scroll",i)}switch(n){case"input":Xi(i),Ol(i,s,!0);break;case"textarea":Xi(i),Dl(i);break;case"select":case"option":break;default:typeof s.onClick=="function"&&(i.onclick=Br)}i=r,t.updateQueue=i,i!==null&&(t.flags|=4)}else{o=r.nodeType===9?r:r.ownerDocument,e==="http://www.w3.org/1999/xhtml"&&(e=du(n)),e==="http://www.w3.org/1999/xhtml"?n==="script"?(e=o.createElement("div"),e.innerHTML="<script><\/script>",e=e.removeChild(e.firstChild)):typeof i.is=="string"?e=o.createElement(n,{is:i.is}):(e=o.createElement(n),n==="select"&&(o=e,i.multiple?o.multiple=!0:i.size&&(o.size=i.size))):e=o.createElementNS(e,n),e[Je]=t,e[Ii]=i,jf(e,t,!1,!1),t.stateNode=e;e:{switch(o=Co(n,i),n){case"dialog":F("cancel",e),F("close",e),r=i;break;case"iframe":case"object":case"embed":F("load",e),r=i;break;case"video":case"audio":for(r=0;r<si.length;r++)F(si[r],e);r=i;break;case"source":F("error",e),r=i;break;case"img":case"image":case"link":F("error",e),F("load",e),r=i;break;case"details":F("toggle",e),r=i;break;case"input":Il(e,i),r=wo(e,i),F("invalid",e);break;case"option":r=i;break;case"select":e._wrapperState={wasMultiple:!!i.multiple},r=U({},i,{value:void 0}),F("invalid",e);break;case"textarea":Ll(e,i),r=_o(e,i),F("invalid",e);break;default:r=i}Eo(n,r),a=r;for(s in a)if(a.hasOwnProperty(s)){var l=a[s];s==="style"?mu(e,l):s==="dangerouslySetInnerHTML"?(l=l?l.__html:void 0,l!=null&&pu(e,l)):s==="children"?typeof l=="string"?(n!=="textarea"||l!=="")&&Si(e,l):typeof l=="number"&&Si(e,""+l):s!=="suppressContentEditableWarning"&&s!=="suppressHydrationWarning"&&s!=="autoFocus"&&(ki.hasOwnProperty(s)?l!=null&&s==="onScroll"&&F("scroll",e):l!=null&&wa(e,s,l,o))}switch(n){case"input":Xi(e),Ol(e,i,!1);break;case"textarea":Xi(e),Dl(e);break;case"option":i.value!=null&&e.setAttribute("value",""+It(i.value));break;case"select":e.multiple=!!i.multiple,s=i.value,s!=null?Sn(e,!!i.multiple,s,!1):i.defaultValue!=null&&Sn(e,!!i.multiple,i.defaultValue,!0);break;default:typeof r.onClick=="function"&&(e.onclick=Br)}switch(n){case"button":case"input":case"select":case"textarea":i=!!i.autoFocus;break e;case"img":i=!0;break e;default:i=!1}}i&&(t.flags|=4)}t.ref!==null&&(t.flags|=512,t.flags|=2097152)}return fe(t),null;case 6:if(e&&t.stateNode!=null)Ff(e,t,e.memoizedProps,i);else{if(typeof i!="string"&&t.stateNode===null)throw Error(C(166));if(n=Ht(Li.current),Ht(Ze.current),ar(t)){if(i=t.stateNode,n=t.memoizedProps,i[Je]=t,(s=i.nodeValue!==n)&&(e=Ae,e!==null))switch(e.tag){case 3:or(i.nodeValue,n,(e.mode&1)!==0);break;case 5:e.memoizedProps.suppressHydrationWarning!==!0&&or(i.nodeValue,n,(e.mode&1)!==0)}s&&(t.flags|=4)}else i=(n.nodeType===9?n:n.ownerDocument).createTextNode(i),i[Je]=t,t.stateNode=i}return fe(t),null;case 13:if(z(H),i=t.memoizedState,e===null||e.memoizedState!==null&&e.memoizedState.dehydrated!==null){if(B&&Me!==null&&t.mode&1&&!(t.flags&128))nf(),On(),t.flags|=98560,s=!1;else if(s=ar(t),i!==null&&i.dehydrated!==null){if(e===null){if(!s)throw Error(C(318));if(s=t.memoizedState,s=s!==null?s.dehydrated:null,!s)throw Error(C(317));s[Je]=t}else On(),!(t.flags&128)&&(t.memoizedState=null),t.flags|=4;fe(t),s=!1}else Ue!==null&&(sa(Ue),Ue=null),s=!0;if(!s)return t.flags&65536?t:null}return t.flags&128?(t.lanes=n,t):(i=i!==null,i!==(e!==null&&e.memoizedState!==null)&&i&&(t.child.flags|=8192,t.mode&1&&(e===null||H.current&1?te===0&&(te=3):tl())),t.updateQueue!==null&&(t.flags|=4),fe(t),null);case 4:return Dn(),Jo(e,t),e===null&&Ni(t.stateNode.containerInfo),fe(t),null;case 10:return $a(t.type._context),fe(t),null;case 17:return be(t.type)&&Hr(),fe(t),null;case 19:if(z(H),s=t.memoizedState,s===null)return fe(t),null;if(i=(t.flags&128)!==0,o=s.rendering,o===null)if(i)Zn(s,!1);else{if(te!==0||e!==null&&e.flags&128)for(e=t.child;e!==null;){if(o=Gr(e),o!==null){for(t.flags|=128,Zn(s,!1),i=o.updateQueue,i!==null&&(t.updateQueue=i,t.flags|=4),t.subtreeFlags=0,i=n,n=t.child;n!==null;)s=n,e=i,s.flags&=14680066,o=s.alternate,o===null?(s.childLanes=0,s.lanes=e,s.child=null,s.subtreeFlags=0,s.memoizedProps=null,s.memoizedState=null,s.updateQueue=null,s.dependencies=null,s.stateNode=null):(s.childLanes=o.childLanes,s.lanes=o.lanes,s.child=o.child,s.subtreeFlags=0,s.deletions=null,s.memoizedProps=o.memoizedProps,s.memoizedState=o.memoizedState,s.updateQueue=o.updateQueue,s.type=o.type,e=o.dependencies,s.dependencies=e===null?null:{lanes:e.lanes,firstContext:e.firstContext}),n=n.sibling;return j(H,H.current&1|2),t.child}e=e.sibling}s.tail!==null&&G()>Rn&&(t.flags|=128,i=!0,Zn(s,!1),t.lanes=4194304)}else{if(!i)if(e=Gr(o),e!==null){if(t.flags|=128,i=!0,n=e.updateQueue,n!==null&&(t.updateQueue=n,t.flags|=4),Zn(s,!0),s.tail===null&&s.tailMode==="hidden"&&!o.alternate&&!B)return fe(t),null}else 2*G()-s.renderingStartTime>Rn&&n!==1073741824&&(t.flags|=128,i=!0,Zn(s,!1),t.lanes=4194304);s.isBackwards?(o.sibling=t.child,t.child=o):(n=s.last,n!==null?n.sibling=o:t.child=o,s.last=o)}return s.tail!==null?(t=s.tail,s.rendering=t,s.tail=t.sibling,s.renderingStartTime=G(),t.sibling=null,n=H.current,j(H,i?n&1|2:n&1),t):(fe(t),null);case 22:case 23:return el(),i=t.memoizedState!==null,e!==null&&e.memoizedState!==null!==i&&(t.flags|=8192),i&&t.mode&1?Ce&1073741824&&(fe(t),t.subtreeFlags&6&&(t.flags|=8192)):fe(t),null;case 24:return null;case 25:return null}throw Error(C(156,t.tag))}function Yh(e,t){switch(xa(t),t.tag){case 1:return be(t.type)&&Hr(),e=t.flags,e&65536?(t.flags=e&-65537|128,t):null;case 3:return Dn(),z(_e),z(pe),Va(),e=t.flags,e&65536&&!(e&128)?(t.flags=e&-65537|128,t):null;case 5:return Ha(t),null;case 13:if(z(H),e=t.memoizedState,e!==null&&e.dehydrated!==null){if(t.alternate===null)throw Error(C(340));On()}return e=t.flags,e&65536?(t.flags=e&-65537|128,t):null;case 19:return z(H),null;case 4:return Dn(),null;case 10:return $a(t.type._context),null;case 22:case 23:return el(),null;case 24:return null;default:return null}}var ur=!1,de=!1,Jh=typeof WeakSet=="function"?WeakSet:Set,A=null;function gn(e,t){var n=e.ref;if(n!==null)if(typeof n=="function")try{n(null)}catch(i){K(e,t,i)}else n.current=null}function Xo(e,t,n){try{n()}catch(i){K(e,t,i)}}var _c=!1;function Xh(e,t){if(Ro=$r,e=Vu(),La(e)){if("selectionStart"in e)var n={start:e.selectionStart,end:e.selectionEnd};else e:{n=(n=e.ownerDocument)&&n.defaultView||window;var i=n.getSelection&&n.getSelection();if(i&&i.rangeCount!==0){n=i.anchorNode;var r=i.anchorOffset,s=i.focusNode;i=i.focusOffset;try{n.nodeType,s.nodeType}catch{n=null;break e}var o=0,a=-1,l=-1,c=0,h=0,u=e,p=null;t:for(;;){for(var g;u!==n||r!==0&&u.nodeType!==3||(a=o+r),u!==s||i!==0&&u.nodeType!==3||(l=o+i),u.nodeType===3&&(o+=u.nodeValue.length),(g=u.firstChild)!==null;)p=u,u=g;for(;;){if(u===e)break t;if(p===n&&++c===r&&(a=o),p===s&&++h===i&&(l=o),(g=u.nextSibling)!==null)break;u=p,p=u.parentNode}u=g}n=a===-1||l===-1?null:{start:a,end:l}}else n=null}n=n||{start:0,end:0}}else n=null;for(Po={focusedElem:e,selectionRange:n},$r=!1,A=t;A!==null;)if(t=A,e=t.child,(t.subtreeFlags&1028)!==0&&e!==null)e.return=t,A=e;else for(;A!==null;){t=A;try{var v=t.alternate;if(t.flags&1024)switch(t.tag){case 0:case 11:case 15:break;case 1:if(v!==null){var y=v.memoizedProps,k=v.memoizedState,d=t.stateNode,f=d.getSnapshotBeforeUpdate(t.elementType===t.type?y:He(t.type,y),k);d.__reactInternalSnapshotBeforeUpdate=f}break;case 3:var m=t.stateNode.containerInfo;m.nodeType===1?m.textContent="":m.nodeType===9&&m.documentElement&&m.removeChild(m.documentElement);break;case 5:case 6:case 4:case 17:break;default:throw Error(C(163))}}catch(w){K(t,t.return,w)}if(e=t.sibling,e!==null){e.return=t.return,A=e;break}A=t.return}return v=_c,_c=!1,v}function hi(e,t,n){var i=t.updateQueue;if(i=i!==null?i.lastEffect:null,i!==null){var r=i=i.next;do{if((r.tag&e)===e){var s=r.destroy;r.destroy=void 0,s!==void 0&&Xo(t,n,s)}r=r.next}while(r!==i)}}function ms(e,t){if(t=t.updateQueue,t=t!==null?t.lastEffect:null,t!==null){var n=t=t.next;do{if((n.tag&e)===e){var i=n.create;n.destroy=i()}n=n.next}while(n!==t)}}function Zo(e){var t=e.ref;if(t!==null){var n=e.stateNode;switch(e.tag){case 5:e=n;break;default:e=n}typeof t=="function"?t(e):t.current=e}}function zf(e){var t=e.alternate;t!==null&&(e.alternate=null,zf(t)),e.child=null,e.deletions=null,e.sibling=null,e.tag===5&&(t=e.stateNode,t!==null&&(delete t[Je],delete t[Ii],delete t[Fo],delete t[xh],delete t[Rh])),e.stateNode=null,e.return=null,e.dependencies=null,e.memoizedProps=null,e.memoizedState=null,e.pendingProps=null,e.stateNode=null,e.updateQueue=null}function Bf(e){return e.tag===5||e.tag===3||e.tag===4}function bc(e){e:for(;;){for(;e.sibling===null;){if(e.return===null||Bf(e.return))return null;e=e.return}for(e.sibling.return=e.return,e=e.sibling;e.tag!==5&&e.tag!==6&&e.tag!==18;){if(e.flags&2||e.child===null||e.tag===4)continue e;e.child.return=e,e=e.child}if(!(e.flags&2))return e.stateNode}}function ea(e,t,n){var i=e.tag;if(i===5||i===6)e=e.stateNode,t?n.nodeType===8?n.parentNode.insertBefore(e,t):n.insertBefore(e,t):(n.nodeType===8?(t=n.parentNode,t.insertBefore(e,n)):(t=n,t.appendChild(e)),n=n._reactRootContainer,n!=null||t.onclick!==null||(t.onclick=Br));else if(i!==4&&(e=e.child,e!==null))for(ea(e,t,n),e=e.sibling;e!==null;)ea(e,t,n),e=e.sibling}function ta(e,t,n){var i=e.tag;if(i===5||i===6)e=e.stateNode,t?n.insertBefore(e,t):n.appendChild(e);else if(i!==4&&(e=e.child,e!==null))for(ta(e,t,n),e=e.sibling;e!==null;)ta(e,t,n),e=e.sibling}var ae=null,Ve=!1;function pt(e,t,n){for(n=n.child;n!==null;)Hf(e,t,n),n=n.sibling}function Hf(e,t,n){if(Xe&&typeof Xe.onCommitFiberUnmount=="function")try{Xe.onCommitFiberUnmount(as,n)}catch{}switch(n.tag){case 5:de||gn(n,t);case 6:var i=ae,r=Ve;ae=null,pt(e,t,n),ae=i,Ve=r,ae!==null&&(Ve?(e=ae,n=n.stateNode,e.nodeType===8?e.parentNode.removeChild(n):e.removeChild(n)):ae.removeChild(n.stateNode));break;case 18:ae!==null&&(Ve?(e=ae,n=n.stateNode,e.nodeType===8?Js(e.parentNode,n):e.nodeType===1&&Js(e,n),Ci(e)):Js(ae,n.stateNode));break;case 4:i=ae,r=Ve,ae=n.stateNode.containerInfo,Ve=!0,pt(e,t,n),ae=i,Ve=r;break;case 0:case 11:case 14:case 15:if(!de&&(i=n.updateQueue,i!==null&&(i=i.lastEffect,i!==null))){r=i=i.next;do{var s=r,o=s.destroy;s=s.tag,o!==void 0&&(s&2||s&4)&&Xo(n,t,o),r=r.next}while(r!==i)}pt(e,t,n);break;case 1:if(!de&&(gn(n,t),i=n.stateNode,typeof i.componentWillUnmount=="function"))try{i.props=n.memoizedProps,i.state=n.memoizedState,i.componentWillUnmount()}catch(a){K(n,t,a)}pt(e,t,n);break;case 21:pt(e,t,n);break;case 22:n.mode&1?(de=(i=de)||n.memoizedState!==null,pt(e,t,n),de=i):pt(e,t,n);break;default:pt(e,t,n)}}function Ec(e){var t=e.updateQueue;if(t!==null){e.updateQueue=null;var n=e.stateNode;n===null&&(n=e.stateNode=new Jh),t.forEach(function(i){var r=am.bind(null,e,i);n.has(i)||(n.add(i),i.then(r,r))})}}function ze(e,t){var n=t.deletions;if(n!==null)for(var i=0;i<n.length;i++){var r=n[i];try{var s=e,o=t,a=o;e:for(;a!==null;){switch(a.tag){case 5:ae=a.stateNode,Ve=!1;break e;case 3:ae=a.stateNode.containerInfo,Ve=!0;break e;case 4:ae=a.stateNode.containerInfo,Ve=!0;break e}a=a.return}if(ae===null)throw Error(C(160));Hf(s,o,r),ae=null,Ve=!1;var l=r.alternate;l!==null&&(l.return=null),r.return=null}catch(c){K(r,t,c)}}if(t.subtreeFlags&12854)for(t=t.child;t!==null;)Vf(t,e),t=t.sibling}function Vf(e,t){var n=e.alternate,i=e.flags;switch(e.tag){case 0:case 11:case 14:case 15:if(ze(t,e),Ge(e),i&4){try{hi(3,e,e.return),ms(3,e)}catch(y){K(e,e.return,y)}try{hi(5,e,e.return)}catch(y){K(e,e.return,y)}}break;case 1:ze(t,e),Ge(e),i&512&&n!==null&&gn(n,n.return);break;case 5:if(ze(t,e),Ge(e),i&512&&n!==null&&gn(n,n.return),e.flags&32){var r=e.stateNode;try{Si(r,"")}catch(y){K(e,e.return,y)}}if(i&4&&(r=e.stateNode,r!=null)){var s=e.memoizedProps,o=n!==null?n.memoizedProps:s,a=e.type,l=e.updateQueue;if(e.updateQueue=null,l!==null)try{a==="input"&&s.type==="radio"&&s.name!=null&&uu(r,s),Co(a,o);var c=Co(a,s);for(o=0;o<l.length;o+=2){var h=l[o],u=l[o+1];h==="style"?mu(r,u):h==="dangerouslySetInnerHTML"?pu(r,u):h==="children"?Si(r,u):wa(r,h,u,c)}switch(a){case"input":ko(r,s);break;case"textarea":fu(r,s);break;case"select":var p=r._wrapperState.wasMultiple;r._wrapperState.wasMultiple=!!s.multiple;var g=s.value;g!=null?Sn(r,!!s.multiple,g,!1):p!==!!s.multiple&&(s.defaultValue!=null?Sn(r,!!s.multiple,s.defaultValue,!0):Sn(r,!!s.multiple,s.multiple?[]:"",!1))}r[Ii]=s}catch(y){K(e,e.return,y)}}break;case 6:if(ze(t,e),Ge(e),i&4){if(e.stateNode===null)throw Error(C(162));r=e.stateNode,s=e.memoizedProps;try{r.nodeValue=s}catch(y){K(e,e.return,y)}}break;case 3:if(ze(t,e),Ge(e),i&4&&n!==null&&n.memoizedState.isDehydrated)try{Ci(t.containerInfo)}catch(y){K(e,e.return,y)}break;case 4:ze(t,e),Ge(e);break;case 13:ze(t,e),Ge(e),r=e.child,r.flags&8192&&(s=r.memoizedState!==null,r.stateNode.isHidden=s,!s||r.alternate!==null&&r.alternate.memoizedState!==null||(Xa=G())),i&4&&Ec(e);break;case 22:if(h=n!==null&&n.memoizedState!==null,e.mode&1?(de=(c=de)||h,ze(t,e),de=c):ze(t,e),Ge(e),i&8192){if(c=e.memoizedState!==null,(e.stateNode.isHidden=c)&&!h&&e.mode&1)for(A=e,h=e.child;h!==null;){for(u=A=h;A!==null;){switch(p=A,g=p.child,p.tag){case 0:case 11:case 14:case 15:hi(4,p,p.return);break;case 1:gn(p,p.return);var v=p.stateNode;if(typeof v.componentWillUnmount=="function"){i=p,n=p.return;try{t=i,v.props=t.memoizedProps,v.state=t.memoizedState,v.componentWillUnmount()}catch(y){K(i,n,y)}}break;case 5:gn(p,p.return);break;case 22:if(p.memoizedState!==null){Mc(u);continue}}g!==null?(g.return=p,A=g):Mc(u)}h=h.sibling}e:for(h=null,u=e;;){if(u.tag===5){if(h===null){h=u;try{r=u.stateNode,c?(s=r.style,typeof s.setProperty=="function"?s.setProperty("display","none","important"):s.display="none"):(a=u.stateNode,l=u.memoizedProps.style,o=l!=null&&l.hasOwnProperty("display")?l.display:null,a.style.display=hu("display",o))}catch(y){K(e,e.return,y)}}}else if(u.tag===6){if(h===null)try{u.stateNode.nodeValue=c?"":u.memoizedProps}catch(y){K(e,e.return,y)}}else if((u.tag!==22&&u.tag!==23||u.memoizedState===null||u===e)&&u.child!==null){u.child.return=u,u=u.child;continue}if(u===e)break e;for(;u.sibling===null;){if(u.return===null||u.return===e)break e;h===u&&(h=null),u=u.return}h===u&&(h=null),u.sibling.return=u.return,u=u.sibling}}break;case 19:ze(t,e),Ge(e),i&4&&Ec(e);break;case 21:break;default:ze(t,e),Ge(e)}}function Ge(e){var t=e.flags;if(t&2){try{e:{for(var n=e.return;n!==null;){if(Bf(n)){var i=n;break e}n=n.return}throw Error(C(160))}switch(i.tag){case 5:var r=i.stateNode;i.flags&32&&(Si(r,""),i.flags&=-33);var s=bc(e);ta(e,s,r);break;case 3:case 4:var o=i.stateNode.containerInfo,a=bc(e);ea(e,a,o);break;default:throw Error(C(161))}}catch(l){K(e,e.return,l)}e.flags&=-3}t&4096&&(e.flags&=-4097)}function Zh(e,t,n){A=e,Uf(e)}function Uf(e,t,n){for(var i=(e.mode&1)!==0;A!==null;){var r=A,s=r.child;if(r.tag===22&&i){var o=r.memoizedState!==null||ur;if(!o){var a=r.alternate,l=a!==null&&a.memoizedState!==null||de;a=ur;var c=de;if(ur=o,(de=l)&&!c)for(A=r;A!==null;)o=A,l=o.child,o.tag===22&&o.memoizedState!==null?Ac(r):l!==null?(l.return=o,A=l):Ac(r);for(;s!==null;)A=s,Uf(s),s=s.sibling;A=r,ur=a,de=c}Cc(e)}else r.subtreeFlags&8772&&s!==null?(s.return=r,A=s):Cc(e)}}function Cc(e){for(;A!==null;){var t=A;if(t.flags&8772){var n=t.alternate;try{if(t.flags&8772)switch(t.tag){case 0:case 11:case 15:de||ms(5,t);break;case 1:var i=t.stateNode;if(t.flags&4&&!de)if(n===null)i.componentDidMount();else{var r=t.elementType===t.type?n.memoizedProps:He(t.type,n.memoizedProps);i.componentDidUpdate(r,n.memoizedState,i.__reactInternalSnapshotBeforeUpdate)}var s=t.updateQueue;s!==null&&cc(t,s,i);break;case 3:var o=t.updateQueue;if(o!==null){if(n=null,t.child!==null)switch(t.child.tag){case 5:n=t.child.stateNode;break;case 1:n=t.child.stateNode}cc(t,o,n)}break;case 5:var a=t.stateNode;if(n===null&&t.flags&4){n=a;var l=t.memoizedProps;switch(t.type){case"button":case"input":case"select":case"textarea":l.autoFocus&&n.focus();break;case"img":l.src&&(n.src=l.src)}}break;case 6:break;case 4:break;case 12:break;case 13:if(t.memoizedState===null){var c=t.alternate;if(c!==null){var h=c.memoizedState;if(h!==null){var u=h.dehydrated;u!==null&&Ci(u)}}}break;case 19:case 17:case 21:case 22:case 23:case 25:break;default:throw Error(C(163))}de||t.flags&512&&Zo(t)}catch(p){K(t,t.return,p)}}if(t===e){A=null;break}if(n=t.sibling,n!==null){n.return=t.return,A=n;break}A=t.return}}function Mc(e){for(;A!==null;){var t=A;if(t===e){A=null;break}var n=t.sibling;if(n!==null){n.return=t.return,A=n;break}A=t.return}}function Ac(e){for(;A!==null;){var t=A;try{switch(t.tag){case 0:case 11:case 15:var n=t.return;try{ms(4,t)}catch(l){K(t,n,l)}break;case 1:var i=t.stateNode;if(typeof i.componentDidMount=="function"){var r=t.return;try{i.componentDidMount()}catch(l){K(t,r,l)}}var s=t.return;try{Zo(t)}catch(l){K(t,s,l)}break;case 5:var o=t.return;try{Zo(t)}catch(l){K(t,o,l)}}}catch(l){K(t,t.return,l)}if(t===e){A=null;break}var a=t.sibling;if(a!==null){a.return=t.return,A=a;break}A=t.return}}var em=Math.ceil,Xr=dt.ReactCurrentDispatcher,Ya=dt.ReactCurrentOwner,Re=dt.ReactCurrentBatchConfig,R=0,re=null,Z=null,le=0,Ce=0,yn=Dt(0),te=0,Pi=null,Jt=0,gs=0,Ja=0,mi=null,ke=null,Xa=0,Rn=1/0,tt=null,Zr=!1,na=null,Mt=null,fr=!1,kt=null,es=0,gi=0,ia=null,Ar=-1,Nr=0;function ge(){return R&6?G():Ar!==-1?Ar:Ar=G()}function At(e){return e.mode&1?R&2&&le!==0?le&-le:jh.transition!==null?(Nr===0&&(Nr=Au()),Nr):(e=P,e!==0||(e=window.event,e=e===void 0?16:xu(e.type)),e):1}function We(e,t,n,i){if(50<gi)throw gi=0,ia=null,Error(C(185));zi(e,n,i),(!(R&2)||e!==re)&&(e===re&&(!(R&2)&&(gs|=n),te===4&&vt(e,le)),Ee(e,i),n===1&&R===0&&!(t.mode&1)&&(Rn=G()+500,ds&&xt()))}function Ee(e,t){var n=e.callbackNode;jp(e,t);var i=jr(e,e===re?le:0);if(i===0)n!==null&&Pl(n),e.callbackNode=null,e.callbackPriority=0;else if(t=i&-i,e.callbackPriority!==t){if(n!=null&&Pl(n),t===1)e.tag===0?Ph(Nc.bind(null,e)):Zu(Nc.bind(null,e)),Lh(function(){!(R&6)&&xt()}),n=null;else{switch(Nu(i)){case 1:n=Ea;break;case 4:n=Cu;break;case 16:n=Pr;break;case 536870912:n=Mu;break;default:n=Pr}n=Xf(n,Kf.bind(null,e))}e.callbackPriority=t,e.callbackNode=n}}function Kf(e,t){if(Ar=-1,Nr=0,R&6)throw Error(C(327));var n=e.callbackNode;if(Mn()&&e.callbackNode!==n)return null;var i=jr(e,e===re?le:0);if(i===0)return null;if(i&30||i&e.expiredLanes||t)t=ts(e,i);else{t=i;var r=R;R|=2;var s=qf();(re!==e||le!==t)&&(tt=null,Rn=G()+500,Wt(e,t));do try{im();break}catch(a){Wf(e,a)}while(!0);ja(),Xr.current=s,R=r,Z!==null?t=0:(re=null,le=0,t=te)}if(t!==0){if(t===2&&(r=Io(e),r!==0&&(i=r,t=ra(e,r))),t===1)throw n=Pi,Wt(e,0),vt(e,i),Ee(e,G()),n;if(t===6)vt(e,i);else{if(r=e.current.alternate,!(i&30)&&!tm(r)&&(t=ts(e,i),t===2&&(s=Io(e),s!==0&&(i=s,t=ra(e,s))),t===1))throw n=Pi,Wt(e,0),vt(e,i),Ee(e,G()),n;switch(e.finishedWork=r,e.finishedLanes=i,t){case 0:case 1:throw Error(C(345));case 2:$t(e,ke,tt);break;case 3:if(vt(e,i),(i&130023424)===i&&(t=Xa+500-G(),10<t)){if(jr(e,0)!==0)break;if(r=e.suspendedLanes,(r&i)!==i){ge(),e.pingedLanes|=e.suspendedLanes&r;break}e.timeoutHandle=$o($t.bind(null,e,ke,tt),t);break}$t(e,ke,tt);break;case 4:if(vt(e,i),(i&4194240)===i)break;for(t=e.eventTimes,r=-1;0<i;){var o=31-Ke(i);s=1<<o,o=t[o],o>r&&(r=o),i&=~s}if(i=r,i=G()-i,i=(120>i?120:480>i?480:1080>i?1080:1920>i?1920:3e3>i?3e3:4320>i?4320:1960*em(i/1960))-i,10<i){e.timeoutHandle=$o($t.bind(null,e,ke,tt),i);break}$t(e,ke,tt);break;case 5:$t(e,ke,tt);break;default:throw Error(C(329))}}}return Ee(e,G()),e.callbackNode===n?Kf.bind(null,e):null}function ra(e,t){var n=mi;return e.current.memoizedState.isDehydrated&&(Wt(e,t).flags|=256),e=ts(e,t),e!==2&&(t=ke,ke=n,t!==null&&sa(t)),e}function sa(e){ke===null?ke=e:ke.push.apply(ke,e)}function tm(e){for(var t=e;;){if(t.flags&16384){var n=t.updateQueue;if(n!==null&&(n=n.stores,n!==null))for(var i=0;i<n.length;i++){var r=n[i],s=r.getSnapshot;r=r.value;try{if(!qe(s(),r))return!1}catch{return!1}}}if(n=t.child,t.subtreeFlags&16384&&n!==null)n.return=t,t=n;else{if(t===e)break;for(;t.sibling===null;){if(t.return===null||t.return===e)return!0;t=t.return}t.sibling.return=t.return,t=t.sibling}}return!0}function vt(e,t){for(t&=~Ja,t&=~gs,e.suspendedLanes|=t,e.pingedLanes&=~t,e=e.expirationTimes;0<t;){var n=31-Ke(t),i=1<<n;e[n]=-1,t&=~i}}function Nc(e){if(R&6)throw Error(C(327));Mn();var t=jr(e,0);if(!(t&1))return Ee(e,G()),null;var n=ts(e,t);if(e.tag!==0&&n===2){var i=Io(e);i!==0&&(t=i,n=ra(e,i))}if(n===1)throw n=Pi,Wt(e,0),vt(e,t),Ee(e,G()),n;if(n===6)throw Error(C(345));return e.finishedWork=e.current.alternate,e.finishedLanes=t,$t(e,ke,tt),Ee(e,G()),null}function Za(e,t){var n=R;R|=1;try{return e(t)}finally{R=n,R===0&&(Rn=G()+500,ds&&xt())}}function Xt(e){kt!==null&&kt.tag===0&&!(R&6)&&Mn();var t=R;R|=1;var n=Re.transition,i=P;try{if(Re.transition=null,P=1,e)return e()}finally{P=i,Re.transition=n,R=t,!(R&6)&&xt()}}function el(){Ce=yn.current,z(yn)}function Wt(e,t){e.finishedWork=null,e.finishedLanes=0;var n=e.timeoutHandle;if(n!==-1&&(e.timeoutHandle=-1,Oh(n)),Z!==null)for(n=Z.return;n!==null;){var i=n;switch(xa(i),i.tag){case 1:i=i.type.childContextTypes,i!=null&&Hr();break;case 3:Dn(),z(_e),z(pe),Va();break;case 5:Ha(i);break;case 4:Dn();break;case 13:z(H);break;case 19:z(H);break;case 10:$a(i.type._context);break;case 22:case 23:el()}n=n.return}if(re=e,Z=e=Nt(e.current,null),le=Ce=t,te=0,Pi=null,Ja=gs=Jt=0,ke=mi=null,Bt!==null){for(t=0;t<Bt.length;t++)if(n=Bt[t],i=n.interleaved,i!==null){n.interleaved=null;var r=i.next,s=n.pending;if(s!==null){var o=s.next;s.next=r,i.next=o}n.pending=i}Bt=null}return e}function Wf(e,t){do{var n=Z;try{if(ja(),Er.current=Jr,Yr){for(var i=V.memoizedState;i!==null;){var r=i.queue;r!==null&&(r.pending=null),i=i.next}Yr=!1}if(Yt=0,ie=ee=V=null,pi=!1,Di=0,Ya.current=null,n===null||n.return===null){te=1,Pi=t,Z=null;break}e:{var s=e,o=n.return,a=n,l=t;if(t=le,a.flags|=32768,l!==null&&typeof l=="object"&&typeof l.then=="function"){var c=l,h=a,u=h.tag;if(!(h.mode&1)&&(u===0||u===11||u===15)){var p=h.alternate;p?(h.updateQueue=p.updateQueue,h.memoizedState=p.memoizedState,h.lanes=p.lanes):(h.updateQueue=null,h.memoizedState=null)}var g=mc(o);if(g!==null){g.flags&=-257,gc(g,o,a,s,t),g.mode&1&&hc(s,c,t),t=g,l=c;var v=t.updateQueue;if(v===null){var y=new Set;y.add(l),t.updateQueue=y}else v.add(l);break e}else{if(!(t&1)){hc(s,c,t),tl();break e}l=Error(C(426))}}else if(B&&a.mode&1){var k=mc(o);if(k!==null){!(k.flags&65536)&&(k.flags|=256),gc(k,o,a,s,t),Ra(xn(l,a));break e}}s=l=xn(l,a),te!==4&&(te=2),mi===null?mi=[s]:mi.push(s),s=o;do{switch(s.tag){case 3:s.flags|=65536,t&=-t,s.lanes|=t;var d=Tf(s,l,t);lc(s,d);break e;case 1:a=l;var f=s.type,m=s.stateNode;if(!(s.flags&128)&&(typeof f.getDerivedStateFromError=="function"||m!==null&&typeof m.componentDidCatch=="function"&&(Mt===null||!Mt.has(m)))){s.flags|=65536,t&=-t,s.lanes|=t;var w=If(s,a,t);lc(s,w);break e}}s=s.return}while(s!==null)}Gf(n)}catch(S){t=S,Z===n&&n!==null&&(Z=n=n.return);continue}break}while(!0)}function qf(){var e=Xr.current;return Xr.current=Jr,e===null?Jr:e}function tl(){(te===0||te===3||te===2)&&(te=4),re===null||!(Jt&268435455)&&!(gs&268435455)||vt(re,le)}function ts(e,t){var n=R;R|=2;var i=qf();(re!==e||le!==t)&&(tt=null,Wt(e,t));do try{nm();break}catch(r){Wf(e,r)}while(!0);if(ja(),R=n,Xr.current=i,Z!==null)throw Error(C(261));return re=null,le=0,te}function nm(){for(;Z!==null;)Qf(Z)}function im(){for(;Z!==null&&!Np();)Qf(Z)}function Qf(e){var t=Jf(e.alternate,e,Ce);e.memoizedProps=e.pendingProps,t===null?Gf(e):Z=t,Ya.current=null}function Gf(e){var t=e;do{var n=t.alternate;if(e=t.return,t.flags&32768){if(n=Yh(n,t),n!==null){n.flags&=32767,Z=n;return}if(e!==null)e.flags|=32768,e.subtreeFlags=0,e.deletions=null;else{te=6,Z=null;return}}else if(n=Gh(n,t,Ce),n!==null){Z=n;return}if(t=t.sibling,t!==null){Z=t;return}Z=t=e}while(t!==null);te===0&&(te=5)}function $t(e,t,n){var i=P,r=Re.transition;try{Re.transition=null,P=1,rm(e,t,n,i)}finally{Re.transition=r,P=i}return null}function rm(e,t,n,i){do Mn();while(kt!==null);if(R&6)throw Error(C(327));n=e.finishedWork;var r=e.finishedLanes;if(n===null)return null;if(e.finishedWork=null,e.finishedLanes=0,n===e.current)throw Error(C(177));e.callbackNode=null,e.callbackPriority=0;var s=n.lanes|n.childLanes;if($p(e,s),e===re&&(Z=re=null,le=0),!(n.subtreeFlags&2064)&&!(n.flags&2064)||fr||(fr=!0,Xf(Pr,function(){return Mn(),null})),s=(n.flags&15990)!==0,n.subtreeFlags&15990||s){s=Re.transition,Re.transition=null;var o=P;P=1;var a=R;R|=4,Ya.current=null,Xh(e,n),Vf(n,e),Eh(Po),$r=!!Ro,Po=Ro=null,e.current=n,Zh(n),Tp(),R=a,P=o,Re.transition=s}else e.current=n;if(fr&&(fr=!1,kt=e,es=r),s=e.pendingLanes,s===0&&(Mt=null),Lp(n.stateNode),Ee(e,G()),t!==null)for(i=e.onRecoverableError,n=0;n<t.length;n++)r=t[n],i(r.value,{componentStack:r.stack,digest:r.digest});if(Zr)throw Zr=!1,e=na,na=null,e;return es&1&&e.tag!==0&&Mn(),s=e.pendingLanes,s&1?e===ia?gi++:(gi=0,ia=e):gi=0,xt(),null}function Mn(){if(kt!==null){var e=Nu(es),t=Re.transition,n=P;try{if(Re.transition=null,P=16>e?16:e,kt===null)var i=!1;else{if(e=kt,kt=null,es=0,R&6)throw Error(C(331));var r=R;for(R|=4,A=e.current;A!==null;){var s=A,o=s.child;if(A.flags&16){var a=s.deletions;if(a!==null){for(var l=0;l<a.length;l++){var c=a[l];for(A=c;A!==null;){var h=A;switch(h.tag){case 0:case 11:case 15:hi(8,h,s)}var u=h.child;if(u!==null)u.return=h,A=u;else for(;A!==null;){h=A;var p=h.sibling,g=h.return;if(zf(h),h===c){A=null;break}if(p!==null){p.return=g,A=p;break}A=g}}}var v=s.alternate;if(v!==null){var y=v.child;if(y!==null){v.child=null;do{var k=y.sibling;y.sibling=null,y=k}while(y!==null)}}A=s}}if(s.subtreeFlags&2064&&o!==null)o.return=s,A=o;else e:for(;A!==null;){if(s=A,s.flags&2048)switch(s.tag){case 0:case 11:case 15:hi(9,s,s.return)}var d=s.sibling;if(d!==null){d.return=s.return,A=d;break e}A=s.return}}var f=e.current;for(A=f;A!==null;){o=A;var m=o.child;if(o.subtreeFlags&2064&&m!==null)m.return=o,A=m;else e:for(o=f;A!==null;){if(a=A,a.flags&2048)try{switch(a.tag){case 0:case 11:case 15:ms(9,a)}}catch(S){K(a,a.return,S)}if(a===o){A=null;break e}var w=a.sibling;if(w!==null){w.return=a.return,A=w;break e}A=a.return}}if(R=r,xt(),Xe&&typeof Xe.onPostCommitFiberRoot=="function")try{Xe.onPostCommitFiberRoot(as,e)}catch{}i=!0}return i}finally{P=n,Re.transition=t}}return!1}function Tc(e,t,n){t=xn(n,t),t=Tf(e,t,1),e=Ct(e,t,1),t=ge(),e!==null&&(zi(e,1,t),Ee(e,t))}function K(e,t,n){if(e.tag===3)Tc(e,e,n);else for(;t!==null;){if(t.tag===3){Tc(t,e,n);break}else if(t.tag===1){var i=t.stateNode;if(typeof t.type.getDerivedStateFromError=="function"||typeof i.componentDidCatch=="function"&&(Mt===null||!Mt.has(i))){e=xn(n,e),e=If(t,e,1),t=Ct(t,e,1),e=ge(),t!==null&&(zi(t,1,e),Ee(t,e));break}}t=t.return}}function sm(e,t,n){var i=e.pingCache;i!==null&&i.delete(t),t=ge(),e.pingedLanes|=e.suspendedLanes&n,re===e&&(le&n)===n&&(te===4||te===3&&(le&130023424)===le&&500>G()-Xa?Wt(e,0):Ja|=n),Ee(e,t)}function Yf(e,t){t===0&&(e.mode&1?(t=tr,tr<<=1,!(tr&130023424)&&(tr=4194304)):t=1);var n=ge();e=ut(e,t),e!==null&&(zi(e,t,n),Ee(e,n))}function om(e){var t=e.memoizedState,n=0;t!==null&&(n=t.retryLane),Yf(e,n)}function am(e,t){var n=0;switch(e.tag){case 13:var i=e.stateNode,r=e.memoizedState;r!==null&&(n=r.retryLane);break;case 19:i=e.stateNode;break;default:throw Error(C(314))}i!==null&&i.delete(t),Yf(e,n)}var Jf;Jf=function(e,t,n){if(e!==null)if(e.memoizedProps!==t.pendingProps||_e.current)Se=!0;else{if(!(e.lanes&n)&&!(t.flags&128))return Se=!1,Qh(e,t,n);Se=!!(e.flags&131072)}else Se=!1,B&&t.flags&1048576&&ef(t,Kr,t.index);switch(t.lanes=0,t.tag){case 2:var i=t.type;Mr(e,t),e=t.pendingProps;var r=In(t,pe.current);Cn(t,n),r=Ka(null,t,i,e,r,n);var s=Wa();return t.flags|=1,typeof r=="object"&&r!==null&&typeof r.render=="function"&&r.$$typeof===void 0?(t.tag=1,t.memoizedState=null,t.updateQueue=null,be(i)?(s=!0,Vr(t)):s=!1,t.memoizedState=r.state!==null&&r.state!==void 0?r.state:null,za(t),r.updater=hs,t.stateNode=r,r._reactInternals=t,Ko(t,i,e,n),t=Qo(null,t,i,!0,s,n)):(t.tag=0,B&&s&&Da(t),he(null,t,r,n),t=t.child),t;case 16:i=t.elementType;e:{switch(Mr(e,t),e=t.pendingProps,r=i._init,i=r(i._payload),t.type=i,r=t.tag=cm(i),e=He(i,e),r){case 0:t=qo(null,t,i,e,n);break e;case 1:t=wc(null,t,i,e,n);break e;case 11:t=yc(null,t,i,e,n);break e;case 14:t=vc(null,t,i,He(i.type,e),n);break e}throw Error(C(306,i,""))}return t;case 0:return i=t.type,r=t.pendingProps,r=t.elementType===i?r:He(i,r),qo(e,t,i,r,n);case 1:return i=t.type,r=t.pendingProps,r=t.elementType===i?r:He(i,r),wc(e,t,i,r,n);case 3:e:{if(xf(t),e===null)throw Error(C(387));i=t.pendingProps,s=t.memoizedState,r=s.element,af(e,t),Qr(t,i,null,n);var o=t.memoizedState;if(i=o.element,s.isDehydrated)if(s={element:i,isDehydrated:!1,cache:o.cache,pendingSuspenseBoundaries:o.pendingSuspenseBoundaries,transitions:o.transitions},t.updateQueue.baseState=s,t.memoizedState=s,t.flags&256){r=xn(Error(C(423)),t),t=kc(e,t,i,n,r);break e}else if(i!==r){r=xn(Error(C(424)),t),t=kc(e,t,i,n,r);break e}else for(Me=Et(t.stateNode.containerInfo.firstChild),Ae=t,B=!0,Ue=null,n=sf(t,null,i,n),t.child=n;n;)n.flags=n.flags&-3|4096,n=n.sibling;else{if(On(),i===r){t=ft(e,t,n);break e}he(e,t,i,n)}t=t.child}return t;case 5:return lf(t),e===null&&Ho(t),i=t.type,r=t.pendingProps,s=e!==null?e.memoizedProps:null,o=r.children,jo(i,r)?o=null:s!==null&&jo(i,s)&&(t.flags|=32),Df(e,t),he(e,t,o,n),t.child;case 6:return e===null&&Ho(t),null;case 13:return Rf(e,t,n);case 4:return Ba(t,t.stateNode.containerInfo),i=t.pendingProps,e===null?t.child=Ln(t,null,i,n):he(e,t,i,n),t.child;case 11:return i=t.type,r=t.pendingProps,r=t.elementType===i?r:He(i,r),yc(e,t,i,r,n);case 7:return he(e,t,t.pendingProps,n),t.child;case 8:return he(e,t,t.pendingProps.children,n),t.child;case 12:return he(e,t,t.pendingProps.children,n),t.child;case 10:e:{if(i=t.type._context,r=t.pendingProps,s=t.memoizedProps,o=r.value,j(Wr,i._currentValue),i._currentValue=o,s!==null)if(qe(s.value,o)){if(s.children===r.children&&!_e.current){t=ft(e,t,n);break e}}else for(s=t.child,s!==null&&(s.return=t);s!==null;){var a=s.dependencies;if(a!==null){o=s.child;for(var l=a.firstContext;l!==null;){if(l.context===i){if(s.tag===1){l=ot(-1,n&-n),l.tag=2;var c=s.updateQueue;if(c!==null){c=c.shared;var h=c.pending;h===null?l.next=l:(l.next=h.next,h.next=l),c.pending=l}}s.lanes|=n,l=s.alternate,l!==null&&(l.lanes|=n),Vo(s.return,n,t),a.lanes|=n;break}l=l.next}}else if(s.tag===10)o=s.type===t.type?null:s.child;else if(s.tag===18){if(o=s.return,o===null)throw Error(C(341));o.lanes|=n,a=o.alternate,a!==null&&(a.lanes|=n),Vo(o,n,t),o=s.sibling}else o=s.child;if(o!==null)o.return=s;else for(o=s;o!==null;){if(o===t){o=null;break}if(s=o.sibling,s!==null){s.return=o.return,o=s;break}o=o.return}s=o}he(e,t,r.children,n),t=t.child}return t;case 9:return r=t.type,i=t.pendingProps.children,Cn(t,n),r=je(r),i=i(r),t.flags|=1,he(e,t,i,n),t.child;case 14:return i=t.type,r=He(i,t.pendingProps),r=He(i.type,r),vc(e,t,i,r,n);case 15:return Of(e,t,t.type,t.pendingProps,n);case 17:return i=t.type,r=t.pendingProps,r=t.elementType===i?r:He(i,r),Mr(e,t),t.tag=1,be(i)?(e=!0,Vr(t)):e=!1,Cn(t,n),Nf(t,i,r),Ko(t,i,r,n),Qo(null,t,i,!0,e,n);case 19:return Pf(e,t,n);case 22:return Lf(e,t,n)}throw Error(C(156,t.tag))};function Xf(e,t){return Eu(e,t)}function lm(e,t,n,i){this.tag=e,this.key=n,this.sibling=this.child=this.return=this.stateNode=this.type=this.elementType=null,this.index=0,this.ref=null,this.pendingProps=t,this.dependencies=this.memoizedState=this.updateQueue=this.memoizedProps=null,this.mode=i,this.subtreeFlags=this.flags=0,this.deletions=null,this.childLanes=this.lanes=0,this.alternate=null}function xe(e,t,n,i){return new lm(e,t,n,i)}function nl(e){return e=e.prototype,!(!e||!e.isReactComponent)}function cm(e){if(typeof e=="function")return nl(e)?1:0;if(e!=null){if(e=e.$$typeof,e===Sa)return 11;if(e===_a)return 14}return 2}function Nt(e,t){var n=e.alternate;return n===null?(n=xe(e.tag,t,e.key,e.mode),n.elementType=e.elementType,n.type=e.type,n.stateNode=e.stateNode,n.alternate=e,e.alternate=n):(n.pendingProps=t,n.type=e.type,n.flags=0,n.subtreeFlags=0,n.deletions=null),n.flags=e.flags&14680064,n.childLanes=e.childLanes,n.lanes=e.lanes,n.child=e.child,n.memoizedProps=e.memoizedProps,n.memoizedState=e.memoizedState,n.updateQueue=e.updateQueue,t=e.dependencies,n.dependencies=t===null?null:{lanes:t.lanes,firstContext:t.firstContext},n.sibling=e.sibling,n.index=e.index,n.ref=e.ref,n}function Tr(e,t,n,i,r,s){var o=2;if(i=e,typeof e=="function")nl(e)&&(o=1);else if(typeof e=="string")o=5;else e:switch(e){case an:return qt(n.children,r,s,t);case ka:o=8,r|=8;break;case mo:return e=xe(12,n,t,r|2),e.elementType=mo,e.lanes=s,e;case go:return e=xe(13,n,t,r),e.elementType=go,e.lanes=s,e;case yo:return e=xe(19,n,t,r),e.elementType=yo,e.lanes=s,e;case au:return ys(n,r,s,t);default:if(typeof e=="object"&&e!==null)switch(e.$$typeof){case su:o=10;break e;case ou:o=9;break e;case Sa:o=11;break e;case _a:o=14;break e;case ht:o=16,i=null;break e}throw Error(C(130,e==null?e:typeof e,""))}return t=xe(o,n,t,r),t.elementType=e,t.type=i,t.lanes=s,t}function qt(e,t,n,i){return e=xe(7,e,i,t),e.lanes=n,e}function ys(e,t,n,i){return e=xe(22,e,i,t),e.elementType=au,e.lanes=n,e.stateNode={isHidden:!1},e}function so(e,t,n){return e=xe(6,e,null,t),e.lanes=n,e}function oo(e,t,n){return t=xe(4,e.children!==null?e.children:[],e.key,t),t.lanes=n,t.stateNode={containerInfo:e.containerInfo,pendingChildren:null,implementation:e.implementation},t}function um(e,t,n,i,r){this.tag=t,this.containerInfo=e,this.finishedWork=this.pingCache=this.current=this.pendingChildren=null,this.timeoutHandle=-1,this.callbackNode=this.pendingContext=this.context=null,this.callbackPriority=0,this.eventTimes=zs(0),this.expirationTimes=zs(-1),this.entangledLanes=this.finishedLanes=this.mutableReadLanes=this.expiredLanes=this.pingedLanes=this.suspendedLanes=this.pendingLanes=0,this.entanglements=zs(0),this.identifierPrefix=i,this.onRecoverableError=r,this.mutableSourceEagerHydrationData=null}function il(e,t,n,i,r,s,o,a,l){return e=new um(e,t,n,a,l),t===1?(t=1,s===!0&&(t|=8)):t=0,s=xe(3,null,null,t),e.current=s,s.stateNode=e,s.memoizedState={element:i,isDehydrated:n,cache:null,transitions:null,pendingSuspenseBoundaries:null},za(s),e}function fm(e,t,n){var i=3<arguments.length&&arguments[3]!==void 0?arguments[3]:null;return{$$typeof:on,key:i==null?null:""+i,children:e,containerInfo:t,implementation:n}}function Zf(e){if(!e)return Ot;e=e._reactInternals;e:{if(tn(e)!==e||e.tag!==1)throw Error(C(170));var t=e;do{switch(t.tag){case 3:t=t.stateNode.context;break e;case 1:if(be(t.type)){t=t.stateNode.__reactInternalMemoizedMergedChildContext;break e}}t=t.return}while(t!==null);throw Error(C(171))}if(e.tag===1){var n=e.type;if(be(n))return Xu(e,n,t)}return t}function ed(e,t,n,i,r,s,o,a,l){return e=il(n,i,!0,e,r,s,o,a,l),e.context=Zf(null),n=e.current,i=ge(),r=At(n),s=ot(i,r),s.callback=t??null,Ct(n,s,r),e.current.lanes=r,zi(e,r,i),Ee(e,i),e}function vs(e,t,n,i){var r=t.current,s=ge(),o=At(r);return n=Zf(n),t.context===null?t.context=n:t.pendingContext=n,t=ot(s,o),t.payload={element:e},i=i===void 0?null:i,i!==null&&(t.callback=i),e=Ct(r,t,o),e!==null&&(We(e,r,o,s),br(e,r,o)),o}function ns(e){if(e=e.current,!e.child)return null;switch(e.child.tag){case 5:return e.child.stateNode;default:return e.child.stateNode}}function Ic(e,t){if(e=e.memoizedState,e!==null&&e.dehydrated!==null){var n=e.retryLane;e.retryLane=n!==0&&n<t?n:t}}function rl(e,t){Ic(e,t),(e=e.alternate)&&Ic(e,t)}function dm(){return null}var td=typeof reportError=="function"?reportError:function(e){console.error(e)};function sl(e){this._internalRoot=e}ws.prototype.render=sl.prototype.render=function(e){var t=this._internalRoot;if(t===null)throw Error(C(409));vs(e,t,null,null)};ws.prototype.unmount=sl.prototype.unmount=function(){var e=this._internalRoot;if(e!==null){this._internalRoot=null;var t=e.containerInfo;Xt(function(){vs(null,e,null,null)}),t[ct]=null}};function ws(e){this._internalRoot=e}ws.prototype.unstable_scheduleHydration=function(e){if(e){var t=Ou();e={blockedOn:null,target:e,priority:t};for(var n=0;n<yt.length&&t!==0&&t<yt[n].priority;n++);yt.splice(n,0,e),n===0&&Du(e)}};function ol(e){return!(!e||e.nodeType!==1&&e.nodeType!==9&&e.nodeType!==11)}function ks(e){return!(!e||e.nodeType!==1&&e.nodeType!==9&&e.nodeType!==11&&(e.nodeType!==8||e.nodeValue!==" react-mount-point-unstable "))}function Oc(){}function pm(e,t,n,i,r){if(r){if(typeof i=="function"){var s=i;i=function(){var c=ns(o);s.call(c)}}var o=ed(t,i,e,0,null,!1,!1,"",Oc);return e._reactRootContainer=o,e[ct]=o.current,Ni(e.nodeType===8?e.parentNode:e),Xt(),o}for(;r=e.lastChild;)e.removeChild(r);if(typeof i=="function"){var a=i;i=function(){var c=ns(l);a.call(c)}}var l=il(e,0,!1,null,null,!1,!1,"",Oc);return e._reactRootContainer=l,e[ct]=l.current,Ni(e.nodeType===8?e.parentNode:e),Xt(function(){vs(t,l,n,i)}),l}function Ss(e,t,n,i,r){var s=n._reactRootContainer;if(s){var o=s;if(typeof r=="function"){var a=r;r=function(){var l=ns(o);a.call(l)}}vs(t,o,e,r)}else o=pm(n,t,e,r,i);return ns(o)}Tu=function(e){switch(e.tag){case 3:var t=e.stateNode;if(t.current.memoizedState.isDehydrated){var n=ri(t.pendingLanes);n!==0&&(Ca(t,n|1),Ee(t,G()),!(R&6)&&(Rn=G()+500,xt()))}break;case 13:Xt(function(){var i=ut(e,1);if(i!==null){var r=ge();We(i,e,1,r)}}),rl(e,1)}};Ma=function(e){if(e.tag===13){var t=ut(e,134217728);if(t!==null){var n=ge();We(t,e,134217728,n)}rl(e,134217728)}};Iu=function(e){if(e.tag===13){var t=At(e),n=ut(e,t);if(n!==null){var i=ge();We(n,e,t,i)}rl(e,t)}};Ou=function(){return P};Lu=function(e,t){var n=P;try{return P=e,t()}finally{P=n}};Ao=function(e,t,n){switch(t){case"input":if(ko(e,n),t=n.name,n.type==="radio"&&t!=null){for(n=e;n.parentNode;)n=n.parentNode;for(n=n.querySelectorAll("input[name="+JSON.stringify(""+t)+'][type="radio"]'),t=0;t<n.length;t++){var i=n[t];if(i!==e&&i.form===e.form){var r=fs(i);if(!r)throw Error(C(90));cu(i),ko(i,r)}}}break;case"textarea":fu(e,n);break;case"select":t=n.value,t!=null&&Sn(e,!!n.multiple,t,!1)}};vu=Za;wu=Xt;var hm={usingClientEntryPoint:!1,Events:[Hi,fn,fs,gu,yu,Za]},ei={findFiberByHostInstance:zt,bundleType:0,version:"18.3.1",rendererPackageName:"react-dom"},mm={bundleType:ei.bundleType,version:ei.version,rendererPackageName:ei.rendererPackageName,rendererConfig:ei.rendererConfig,overrideHookState:null,overrideHookStateDeletePath:null,overrideHookStateRenamePath:null,overrideProps:null,overridePropsDeletePath:null,overridePropsRenamePath:null,setErrorHandler:null,setSuspenseHandler:null,scheduleUpdate:null,currentDispatcherRef:dt.ReactCurrentDispatcher,findHostInstanceByFiber:function(e){return e=_u(e),e===null?null:e.stateNode},findFiberByHostInstance:ei.findFiberByHostInstance||dm,findHostInstancesForRefresh:null,scheduleRefresh:null,scheduleRoot:null,setRefreshHandler:null,getCurrentFiber:null,reconcilerVersion:"18.3.1-next-f1338f8080-20240426"};if(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__<"u"){var dr=__REACT_DEVTOOLS_GLOBAL_HOOK__;if(!dr.isDisabled&&dr.supportsFiber)try{as=dr.inject(mm),Xe=dr}catch{}}Te.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED=hm;Te.createPortal=function(e,t){var n=2<arguments.length&&arguments[2]!==void 0?arguments[2]:null;if(!ol(t))throw Error(C(200));return fm(e,t,null,n)};Te.createRoot=function(e,t){if(!ol(e))throw Error(C(299));var n=!1,i="",r=td;return t!=null&&(t.unstable_strictMode===!0&&(n=!0),t.identifierPrefix!==void 0&&(i=t.identifierPrefix),t.onRecoverableError!==void 0&&(r=t.onRecoverableError)),t=il(e,1,!1,null,null,n,!1,i,r),e[ct]=t.current,Ni(e.nodeType===8?e.parentNode:e),new sl(t)};Te.findDOMNode=function(e){if(e==null)return null;if(e.nodeType===1)return e;var t=e._reactInternals;if(t===void 0)throw typeof e.render=="function"?Error(C(188)):(e=Object.keys(e).join(","),Error(C(268,e)));return e=_u(t),e=e===null?null:e.stateNode,e};Te.flushSync=function(e){return Xt(e)};Te.hydrate=function(e,t,n){if(!ks(t))throw Error(C(200));return Ss(null,e,t,!0,n)};Te.hydrateRoot=function(e,t,n){if(!ol(e))throw Error(C(405));var i=n!=null&&n.hydratedSources||null,r=!1,s="",o=td;if(n!=null&&(n.unstable_strictMode===!0&&(r=!0),n.identifierPrefix!==void 0&&(s=n.identifierPrefix),n.onRecoverableError!==void 0&&(o=n.onRecoverableError)),t=ed(t,null,e,1,n??null,r,!1,s,o),e[ct]=t.current,Ni(e),i)for(e=0;e<i.length;e++)n=i[e],r=n._getVersion,r=r(n._source),t.mutableSourceEagerHydrationData==null?t.mutableSourceEagerHydrationData=[n,r]:t.mutableSourceEagerHydrationData.push(n,r);return new ws(t)};Te.render=function(e,t,n){if(!ks(t))throw Error(C(200));return Ss(null,e,t,!1,n)};Te.unmountComponentAtNode=function(e){if(!ks(e))throw Error(C(40));return e._reactRootContainer?(Xt(function(){Ss(null,null,e,!1,function(){e._reactRootContainer=null,e[ct]=null})}),!0):!1};Te.unstable_batchedUpdates=Za;Te.unstable_renderSubtreeIntoContainer=function(e,t,n,i){if(!ks(n))throw Error(C(200));if(e==null||e._reactInternals===void 0)throw Error(C(38));return Ss(e,t,n,!1,i)};Te.version="18.3.1-next-f1338f8080-20240426";function nd(){if(!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__>"u"||typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE!="function"))try{__REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(nd)}catch(e){console.error(e)}}nd(),tu.exports=Te;var gm=tu.exports,ym,Lc=gm;ym=Ml.createRoot=Lc.createRoot,Ml.hydrateRoot=Lc.hydrateRoot;const id="/api/v1",oa="eos.token";function vm(){try{return localStorage.getItem(oa)}catch{return null}}function rd(e){try{e?localStorage.setItem(oa,e):localStorage.removeItem(oa)}catch{}}class wm extends Error{constructor(t,n,i){super(n),this.status=t,this.body=i}}async function yi(e,t={}){const n={...t.headers},i=vm();i&&(n.Authorization=`Bearer ${i}`);let r=t.body;t.json!==void 0&&(n["Content-Type"]="application/json",r=JSON.stringify(t.json));const s=await fetch(`${id}${e}`,{...t,headers:n,body:r});if(s.status===204)return;const o=await s.json().catch(()=>{});if(!s.ok)throw new wm(s.status,(o==null?void 0:o.detail)??s.statusText,o);return o}async function l0(){try{const e=await fetch(`${id}/health`,{signal:AbortSignal.timeout(2500),headers:{Accept:"application/json"}});if(!e.ok)return!1;const t=await e.json().catch(()=>null);return(t==null?void 0:t.status)==="ok"}catch{return!1}}function km(e){return{plan:e.plan,academyType:e.academy_type,modules:new Set(e.modules),moduleNames:new Set(e.module_names),upgradableModules:e.upgradable_modules,limits:e.limits}}async function c0(){const e=await yi("/identity/auth/me");if(!e.organisation_id)return{me:e,organisation:null,entitlement:null,trialEndsAt:null,subscriptionStatus:null};const[t,n]=await Promise.all([yi("/tenancy/organisation"),yi("/tenancy/organisation/entitlement")]);return{me:e,organisation:t,entitlement:km(n),trialEndsAt:n.trial_ends_at,subscriptionStatus:n.subscription_status}}async function u0(e,t,n){const i=await yi("/identity/auth/login",{method:"POST",json:{email:e,password:t,organisation_slug:n||void 0}});rd(i.token)}function f0(){rd(null)}async function d0(e){return yi("/billing/subscription/upgrade",{method:"POST",json:{plan:e}})}const al=Symbol.for("yaml.alias"),aa=Symbol.for("yaml.document"),Tt=Symbol.for("yaml.map"),sd=Symbol.for("yaml.pair"),et=Symbol.for("yaml.scalar"),Bn=Symbol.for("yaml.seq"),Fe=Symbol.for("yaml.node.type"),Hn=e=>!!e&&typeof e=="object"&&e[Fe]===al,_s=e=>!!e&&typeof e=="object"&&e[Fe]===aa,Ui=e=>!!e&&typeof e=="object"&&e[Fe]===Tt,X=e=>!!e&&typeof e=="object"&&e[Fe]===sd,$=e=>!!e&&typeof e=="object"&&e[Fe]===et,Ki=e=>!!e&&typeof e=="object"&&e[Fe]===Bn;function Y(e){if(e&&typeof e=="object")switch(e[Fe]){case Tt:case Bn:return!0}return!1}function J(e){if(e&&typeof e=="object")switch(e[Fe]){case al:case Tt:case et:case Bn:return!0}return!1}const od=e=>($(e)||Y(e))&&!!e.anchor,Ft=Symbol("break visit"),Sm=Symbol("skip children"),vi=Symbol("remove node");function Vn(e,t){const n=_m(t);_s(e)?vn(null,e.contents,n,Object.freeze([e]))===vi&&(e.contents=null):vn(null,e,n,Object.freeze([]))}Vn.BREAK=Ft;Vn.SKIP=Sm;Vn.REMOVE=vi;function vn(e,t,n,i){const r=bm(e,t,n,i);if(J(r)||X(r))return Em(e,i,r),vn(e,r,n,i);if(typeof r!="symbol"){if(Y(t)){i=Object.freeze(i.concat(t));for(let s=0;s<t.items.length;++s){const o=vn(s,t.items[s],n,i);if(typeof o=="number")s=o-1;else{if(o===Ft)return Ft;o===vi&&(t.items.splice(s,1),s-=1)}}}else if(X(t)){i=Object.freeze(i.concat(t));const s=vn("key",t.key,n,i);if(s===Ft)return Ft;s===vi&&(t.key=null);const o=vn("value",t.value,n,i);if(o===Ft)return Ft;o===vi&&(t.value=null)}}return r}function _m(e){return typeof e=="object"&&(e.Collection||e.Node||e.Value)?Object.assign({Alias:e.Node,Map:e.Node,Scalar:e.Node,Seq:e.Node},e.Value&&{Map:e.Value,Scalar:e.Value,Seq:e.Value},e.Collection&&{Map:e.Collection,Seq:e.Collection},e):e}function bm(e,t,n,i){var r,s,o,a,l;if(typeof n=="function")return n(e,t,i);if(Ui(t))return(r=n.Map)==null?void 0:r.call(n,e,t,i);if(Ki(t))return(s=n.Seq)==null?void 0:s.call(n,e,t,i);if(X(t))return(o=n.Pair)==null?void 0:o.call(n,e,t,i);if($(t))return(a=n.Scalar)==null?void 0:a.call(n,e,t,i);if(Hn(t))return(l=n.Alias)==null?void 0:l.call(n,e,t,i)}function Em(e,t,n){const i=t[t.length-1];if(Y(i))i.items[e]=n;else if(X(i))e==="key"?i.key=n:i.value=n;else if(_s(i))i.contents=n;else{const r=Hn(i)?"alias":"scalar";throw new Error(`Cannot replace node with ${r} parent`)}}const Cm={"!":"%21",",":"%2C","[":"%5B","]":"%5D","{":"%7B","}":"%7D"},Mm=e=>e.replace(/[!,[\]{}]/g,t=>Cm[t]);class me{constructor(t,n){this.docStart=null,this.docEnd=!1,this.yaml=Object.assign({},me.defaultYaml,t),this.tags=Object.assign({},me.defaultTags,n)}clone(){const t=new me(this.yaml,this.tags);return t.docStart=this.docStart,t}atDocument(){const t=new me(this.yaml,this.tags);switch(this.yaml.version){case"1.1":this.atNextDocument=!0;break;case"1.2":this.atNextDocument=!1,this.yaml={explicit:me.defaultYaml.explicit,version:"1.2"},this.tags=Object.assign({},me.defaultTags);break}return t}add(t,n){this.atNextDocument&&(this.yaml={explicit:me.defaultYaml.explicit,version:"1.1"},this.tags=Object.assign({},me.defaultTags),this.atNextDocument=!1);const i=t.trim().split(/[ \t]+/),r=i.shift();switch(r){case"%TAG":{if(i.length!==2&&(n(0,"%TAG directive should contain exactly two parts"),i.length<2))return!1;const[s,o]=i;return this.tags[s]=o,!0}case"%YAML":{if(this.yaml.explicit=!0,i.length!==1)return n(0,"%YAML directive should contain exactly one part"),!1;const[s]=i;if(s==="1.1"||s==="1.2")return this.yaml.version=s,!0;{const o=/^\d+\.\d+$/.test(s);return n(6,`Unsupported YAML version ${s}`,o),!1}}default:return n(0,`Unknown directive ${r}`,!0),!1}}tagName(t,n){if(t==="!")return"!";if(t[0]!=="!")return n(`Not a valid tag: ${t}`),null;if(t[1]==="<"){const o=t.slice(2,-1);return o==="!"||o==="!!"?(n(`Verbatim tags aren't resolved, so ${t} is invalid.`),null):(t[t.length-1]!==">"&&n("Verbatim tags must end with a >"),o)}const[,i,r]=t.match(/^(.*!)([^!]*)$/s);r||n(`The ${t} tag has no suffix`);const s=this.tags[i];if(s)try{return s+decodeURIComponent(r)}catch(o){return n(String(o)),null}return i==="!"?t:(n(`Could not resolve tag: ${t}`),null)}tagString(t){for(const[n,i]of Object.entries(this.tags))if(t.startsWith(i))return n+Mm(t.substring(i.length));return t[0]==="!"?t:`!<${t}>`}toString(t){const n=this.yaml.explicit?[`%YAML ${this.yaml.version||"1.2"}`]:[],i=Object.entries(this.tags);let r;if(t&&i.length>0&&J(t.contents)){const s={};Vn(t.contents,(o,a)=>{J(a)&&a.tag&&(s[a.tag]=!0)}),r=Object.keys(s)}else r=[];for(const[s,o]of i)s==="!!"&&o==="tag:yaml.org,2002:"||(!t||r.some(a=>a.startsWith(o)))&&n.push(`%TAG ${s} ${o}`);return n.join(`
`)}}me.defaultYaml={explicit:!1,version:"1.2"};me.defaultTags={"!!":"tag:yaml.org,2002:"};function ad(e){if(/[\x00-\x19\s,[\]{}]/.test(e)){const n=`Anchor must not contain whitespace or control characters: ${JSON.stringify(e)}`;throw new Error(n)}return!0}function ld(e){const t=new Set;return Vn(e,{Value(n,i){i.anchor&&t.add(i.anchor)}}),t}function cd(e,t){for(let n=1;;++n){const i=`${e}${n}`;if(!t.has(i))return i}}function Am(e,t){const n=[],i=new Map;let r=null;return{onAnchor:s=>{n.push(s),r??(r=ld(e));const o=cd(t,r);return r.add(o),o},setAnchors:()=>{for(const s of n){const o=i.get(s);if(typeof o=="object"&&o.anchor&&($(o.node)||Y(o.node)))o.node.anchor=o.anchor;else{const a=new Error("Failed to resolve repeated object (this should not happen)");throw a.source=s,a}}},sourceObjects:i}}function wn(e,t,n,i){if(i&&typeof i=="object")if(Array.isArray(i))for(let r=0,s=i.length;r<s;++r){const o=i[r],a=wn(e,i,String(r),o);a===void 0?delete i[r]:a!==o&&(i[r]=a)}else if(i instanceof Map)for(const r of Array.from(i.keys())){const s=i.get(r),o=wn(e,i,r,s);o===void 0?i.delete(r):o!==s&&i.set(r,o)}else if(i instanceof Set)for(const r of Array.from(i)){const s=wn(e,i,r,r);s===void 0?i.delete(r):s!==r&&(i.delete(r),i.add(s))}else for(const[r,s]of Object.entries(i)){const o=wn(e,i,r,s);o===void 0?delete i[r]:o!==s&&(i[r]=o)}return e.call(t,n,i)}function Pe(e,t,n){if(Array.isArray(e))return e.map((i,r)=>Pe(i,String(r),n));if(e&&typeof e.toJSON=="function"){if(!n||!od(e))return e.toJSON(t,n);const i={aliasCount:0,count:1,res:void 0};n.anchors.set(e,i),n.onCreate=s=>{i.res=s,delete n.onCreate};const r=e.toJSON(t,n);return n.onCreate&&n.onCreate(r),r}return typeof e=="bigint"&&!(n!=null&&n.keep)?Number(e):e}class ll{constructor(t){Object.defineProperty(this,Fe,{value:t})}clone(){const t=Object.create(Object.getPrototypeOf(this),Object.getOwnPropertyDescriptors(this));return this.range&&(t.range=this.range.slice()),t}toJS(t,{mapAsMap:n,maxAliasCount:i,onAnchor:r,reviver:s}={}){if(!_s(t))throw new TypeError("A document argument is required");const o={anchors:new Map,doc:t,keep:!0,mapAsMap:n===!0,mapKeyWarned:!1,maxAliasCount:typeof i=="number"?i:100},a=Pe(this,"",o);if(typeof r=="function")for(const{count:l,res:c}of o.anchors.values())r(c,l);return typeof s=="function"?wn(s,{"":a},"",a):a}}class cl extends ll{constructor(t){super(al),this.source=t,Object.defineProperty(this,"tag",{set(){throw new Error("Alias nodes cannot have tags")}})}resolve(t,n){if((n==null?void 0:n.maxAliasCount)===0)throw new ReferenceError("Alias resolution is disabled");let i;n!=null&&n.aliasResolveCache?i=n.aliasResolveCache:(i=[],Vn(t,{Node:(s,o)=>{(Hn(o)||od(o))&&i.push(o)}}),n&&(n.aliasResolveCache=i));let r;for(const s of i){if(s===this)break;s.anchor===this.source&&(r=s)}if(r&&n){const{anchors:s,doc:o,maxAliasCount:a}=n;let l=s.get(r);if(l||(Pe(r,null,n),l=s.get(r)),(l==null?void 0:l.res)===void 0){const c="This should not happen: Alias anchor was not resolved?";throw new ReferenceError(c)}if(a>=0&&(l.count+=1,l.aliasCount===0&&(l.aliasCount=Ir(o,r,s)),l.count*l.aliasCount>a)){const c="Excessive alias count indicates a resource exhaustion attack";throw new ReferenceError(c)}}return r}toJSON(t,n){if(!n)return{source:this.source};const i=this.resolve(n.doc,n);if(!i){const r=`Unresolved alias (the anchor must be set before the alias): ${this.source}`;throw new ReferenceError(r)}return n.anchors.get(i).res}toString(t,n,i){const r=`*${this.source}`;if(t){if(ad(this.source),t.options.verifyAliasOrder&&!t.anchors.has(this.source)){const s=`Unresolved alias (the anchor must be set before the alias): ${this.source}`;throw new Error(s)}if(t.implicitKey)return`${r} `}return r}}function Ir(e,t,n){if(Hn(t)){const i=t.resolve(e),r=n&&i&&n.get(i);return r?r.count*r.aliasCount:0}else if(Y(t)){let i=0;for(const r of t.items){const s=Ir(e,r,n);s>i&&(i=s)}return i}else if(X(t)){const i=Ir(e,t.key,n),r=Ir(e,t.value,n);return Math.max(i,r)}return 1}const ud=e=>!e||typeof e!="function"&&typeof e!="object";class O extends ll{constructor(t){super(et),this.value=t}toJSON(t,n){return n!=null&&n.keep?this.value:Pe(this.value,t,n)}toString(){return String(this.value)}}O.BLOCK_FOLDED="BLOCK_FOLDED";O.BLOCK_LITERAL="BLOCK_LITERAL";O.PLAIN="PLAIN";O.QUOTE_DOUBLE="QUOTE_DOUBLE";O.QUOTE_SINGLE="QUOTE_SINGLE";const Nm="tag:yaml.org,2002:";function Tm(e,t,n){if(t){const i=n.filter(s=>s.tag===t),r=i.find(s=>!s.format)??i[0];if(!r)throw new Error(`Tag ${t} not found`);return r}return n.find(i=>{var r;return((r=i.identify)==null?void 0:r.call(i,e))&&!i.format})}function ji(e,t,n){var u,p,g;if(_s(e)&&(e=e.contents),J(e))return e;if(X(e)){const v=(p=(u=n.schema[Tt]).createNode)==null?void 0:p.call(u,n.schema,null,n);return v.items.push(e),v}(e instanceof String||e instanceof Number||e instanceof Boolean||typeof BigInt<"u"&&e instanceof BigInt)&&(e=e.valueOf());const{aliasDuplicateObjects:i,onAnchor:r,onTagObj:s,schema:o,sourceObjects:a}=n;let l;if(i&&e&&typeof e=="object"){if(l=a.get(e),l)return l.anchor??(l.anchor=r(e)),new cl(l.anchor);l={anchor:null,node:null},a.set(e,l)}t!=null&&t.startsWith("!!")&&(t=Nm+t.slice(2));let c=Tm(e,t,o.tags);if(!c){if(e&&typeof e.toJSON=="function"&&(e=e.toJSON()),!e||typeof e!="object"){const v=new O(e);return l&&(l.node=v),v}c=e instanceof Map?o[Tt]:Symbol.iterator in Object(e)?o[Bn]:o[Tt]}s&&(s(c),delete n.onTagObj);const h=c!=null&&c.createNode?c.createNode(n.schema,e,n):typeof((g=c==null?void 0:c.nodeClass)==null?void 0:g.from)=="function"?c.nodeClass.from(n.schema,e,n):new O(e);return t?h.tag=t:c.default||(h.tag=c.tag),l&&(l.node=h),h}function is(e,t,n){let i=n;for(let r=t.length-1;r>=0;--r){const s=t[r];if(typeof s=="number"&&Number.isInteger(s)&&s>=0){const o=[];o[s]=i,i=o}else i=new Map([[s,i]])}return ji(i,void 0,{aliasDuplicateObjects:!1,keepUndefined:!1,onAnchor:()=>{throw new Error("This should not happen, please report a bug.")},schema:e,sourceObjects:new Map})}const oi=e=>e==null||typeof e=="object"&&!!e[Symbol.iterator]().next().done;class fd extends ll{constructor(t,n){super(t),Object.defineProperty(this,"schema",{value:n,configurable:!0,enumerable:!1,writable:!0})}clone(t){const n=Object.create(Object.getPrototypeOf(this),Object.getOwnPropertyDescriptors(this));return t&&(n.schema=t),n.items=n.items.map(i=>J(i)||X(i)?i.clone(t):i),this.range&&(n.range=this.range.slice()),n}addIn(t,n){if(oi(t))this.add(n);else{const[i,...r]=t,s=this.get(i,!0);if(Y(s))s.addIn(r,n);else if(s===void 0&&this.schema)this.set(i,is(this.schema,r,n));else throw new Error(`Expected YAML collection at ${i}. Remaining path: ${r}`)}}deleteIn(t){const[n,...i]=t;if(i.length===0)return this.delete(n);const r=this.get(n,!0);if(Y(r))return r.deleteIn(i);throw new Error(`Expected YAML collection at ${n}. Remaining path: ${i}`)}getIn(t,n){const[i,...r]=t,s=this.get(i,!0);return r.length===0?!n&&$(s)?s.value:s:Y(s)?s.getIn(r,n):void 0}hasAllNullValues(t){return this.items.every(n=>{if(!X(n))return!1;const i=n.value;return i==null||t&&$(i)&&i.value==null&&!i.commentBefore&&!i.comment&&!i.tag})}hasIn(t){const[n,...i]=t;if(i.length===0)return this.has(n);const r=this.get(n,!0);return Y(r)?r.hasIn(i):!1}setIn(t,n){const[i,...r]=t;if(r.length===0)this.set(i,n);else{const s=this.get(i,!0);if(Y(s))s.setIn(r,n);else if(s===void 0&&this.schema)this.set(i,is(this.schema,r,n));else throw new Error(`Expected YAML collection at ${i}. Remaining path: ${r}`)}}}const Im=e=>e.replace(/^(?!$)(?: $)?/gm,"#");function st(e,t){return/^\n+$/.test(e)?e.substring(1):t?e.replace(/^(?! *$)/gm,t):e}const Vt=(e,t,n)=>e.endsWith(`
`)?st(n,t):n.includes(`
`)?`
`+st(n,t):(e.endsWith(" ")?"":" ")+n,dd="flow",la="block",Or="quoted";function bs(e,t,n="flow",{indentAtStart:i,lineWidth:r=80,minContentWidth:s=20,onFold:o,onOverflow:a}={}){if(!r||r<0)return e;r<s&&(s=0);const l=Math.max(1+s,1+r-t.length);if(e.length<=l)return e;const c=[],h={};let u=r-t.length;typeof i=="number"&&(i>r-Math.max(2,s)?c.push(0):u=r-i);let p,g,v=!1,y=-1,k=-1,d=-1;n===la&&(y=Dc(e,y,t.length),y!==-1&&(u=y+l));for(let m;m=e[y+=1];){if(n===Or&&m==="\\"){switch(k=y,e[y+1]){case"x":y+=3;break;case"u":y+=5;break;case"U":y+=9;break;default:y+=1}d=y}if(m===`
`)n===la&&(y=Dc(e,y,t.length)),u=y+t.length+l,p=void 0;else{if(m===" "&&g&&g!==" "&&g!==`
`&&g!=="	"){const w=e[y+1];w&&w!==" "&&w!==`
`&&w!=="	"&&(p=y)}if(y>=u)if(p)c.push(p),u=p+l,p=void 0;else if(n===Or){for(;g===" "||g==="	";)g=m,m=e[y+=1],v=!0;const w=y>d+1?y-2:k-1;if(h[w])return e;c.push(w),h[w]=!0,u=w+l,p=void 0}else v=!0}g=m}if(v&&a&&a(),c.length===0)return e;o&&o();let f=e.slice(0,c[0]);for(let m=0;m<c.length;++m){const w=c[m],S=c[m+1]||e.length;w===0?f=`
${t}${e.slice(0,S)}`:(n===Or&&h[w]&&(f+=`${e[w]}\\`),f+=`
${t}${e.slice(w+1,S)}`)}return f}function Dc(e,t,n){let i=t,r=t+1,s=e[r];for(;s===" "||s==="	";)if(t<r+n)s=e[++t];else{do s=e[++t];while(s&&s!==`
`);i=t,r=t+1,s=e[r]}return i}const Es=(e,t)=>({indentAtStart:t?e.indent.length:e.indentAtStart,lineWidth:e.options.lineWidth,minContentWidth:e.options.minContentWidth}),Cs=e=>/^(%|---|\.\.\.)/m.test(e);function Om(e,t,n){if(!t||t<0)return!1;const i=t-n,r=e.length;if(r<=i)return!1;for(let s=0,o=0;s<r;++s)if(e[s]===`
`){if(s-o>i)return!0;if(o=s+1,r-o<=i)return!1}return!0}function wi(e,t){const n=JSON.stringify(e);if(t.options.doubleQuotedAsJSON)return n;const{implicitKey:i}=t,r=t.options.doubleQuotedMinMultiLineLength,s=t.indent||(Cs(e)?"  ":"");let o="",a=0;for(let l=0,c=n[l];c;c=n[++l])if(c===" "&&n[l+1]==="\\"&&n[l+2]==="n"&&(o+=n.slice(a,l)+"\\ ",l+=1,a=l,c="\\"),c==="\\")switch(n[l+1]){case"u":{o+=n.slice(a,l);const h=n.substr(l+2,4);switch(h){case"0000":o+="\\0";break;case"0007":o+="\\a";break;case"000b":o+="\\v";break;case"001b":o+="\\e";break;case"0085":o+="\\N";break;case"00a0":o+="\\_";break;case"2028":o+="\\L";break;case"2029":o+="\\P";break;default:h.substr(0,2)==="00"?o+="\\x"+h.substr(2):o+=n.substr(l,6)}l+=5,a=l+1}break;case"n":if(i||n[l+2]==='"'||n.length<r)l+=1;else{for(o+=n.slice(a,l)+`

`;n[l+2]==="\\"&&n[l+3]==="n"&&n[l+4]!=='"';)o+=`
`,l+=2;o+=s,n[l+2]===" "&&(o+="\\"),l+=1,a=l+1}break;default:l+=1}return o=a?o+n.slice(a):n,i?o:bs(o,s,Or,Es(t,!1))}function ca(e,t){if(t.options.singleQuote===!1||t.implicitKey&&e.includes(`
`)||/[ \t]\n|\n[ \t]/.test(e))return wi(e,t);const n=t.indent||(Cs(e)?"  ":""),i="'"+e.replace(/'/g,"''").replace(/\n+/g,`$&
${n}`)+"'";return t.implicitKey?i:bs(i,n,dd,Es(t,!1))}function kn(e,t){const{singleQuote:n}=t.options;let i;if(n===!1)i=wi;else{const r=e.includes('"'),s=e.includes("'");r&&!s?i=ca:s&&!r?i=wi:i=n?ca:wi}return i(e,t)}let ua;try{ua=new RegExp(`(^|(?<!
))
+(?!
|$)`,"g")}catch{ua=/\n+(?!\n|$)/g}function Lr({comment:e,type:t,value:n},i,r,s){const{blockQuote:o,commentString:a,lineWidth:l}=i.options;if(!o||/\n[\t ]+$/.test(n))return kn(n,i);const c=i.indent||(i.forceBlockIndent||Cs(n)?"  ":""),h=o==="literal"?!0:o==="folded"||t===O.BLOCK_FOLDED?!1:t===O.BLOCK_LITERAL?!0:!Om(n,l,c.length);if(!n)return h?`|
`:`>
`;let u,p;for(p=n.length;p>0;--p){const S=n[p-1];if(S!==`
`&&S!=="	"&&S!==" ")break}let g=n.substring(p);const v=g.indexOf(`
`);v===-1?u="-":n===g||v!==g.length-1?(u="+",s&&s()):u="",g&&(n=n.slice(0,-g.length),g[g.length-1]===`
`&&(g=g.slice(0,-1)),g=g.replace(ua,`$&${c}`));let y=!1,k,d=-1;for(k=0;k<n.length;++k){const S=n[k];if(S===" ")y=!0;else if(S===`
`)d=k;else break}let f=n.substring(0,d<k?d+1:k);f&&(n=n.substring(f.length),f=f.replace(/\n+/g,`$&${c}`));let w=(y?c?"2":"1":"")+u;if(e&&(w+=" "+a(e.replace(/ ?[\r\n]+/g," ")),r&&r()),!h){const S=n.replace(/\n+/g,`
$&`).replace(/(?:^|\n)([\t ].*)(?:([\n\t ]*)\n(?![\n\t ]))?/g,"$1$2").replace(/\n+/g,`$&${c}`);let M=!1;const E=Es(i,!0);o!=="folded"&&t!==O.BLOCK_FOLDED&&(E.onOverflow=()=>{M=!0});const _=bs(`${f}${S}${g}`,c,la,E);if(!M)return`>${w}
${c}${_}`}return n=n.replace(/\n+/g,`$&${c}`),`|${w}
${c}${f}${n}${g}`}function Lm(e,t,n,i){const{type:r,value:s}=e,{actualString:o,implicitKey:a,indent:l,indentStep:c,inFlow:h}=t;if(a&&s.includes(`
`)||h&&/[[\]{},]/.test(s))return kn(s,t);if(/^[\n\t ,[\]{}#&*!|>'"%@`]|^[?-]$|^[?-][ \t]|[\n:][ \t]|[ \t]\n|[\n\t ]#|[\n\t :]$/.test(s))return a||h||!s.includes(`
`)?kn(s,t):Lr(e,t,n,i);if(!a&&!h&&r!==O.PLAIN&&s.includes(`
`))return Lr(e,t,n,i);if(Cs(s)){if(l==="")return t.forceBlockIndent=!0,Lr(e,t,n,i);if(a&&l===c)return kn(s,t)}const u=s.replace(/\n+/g,`$&
${l}`);if(o){const p=y=>{var k;return y.default&&y.tag!=="tag:yaml.org,2002:str"&&((k=y.test)==null?void 0:k.test(u))},{compat:g,tags:v}=t.doc.schema;if(v.some(p)||g!=null&&g.some(p))return kn(s,t)}return a?u:bs(u,l,dd,Es(t,!1))}function ul(e,t,n,i){const{implicitKey:r,inFlow:s}=t,o=typeof e.value=="string"?e:Object.assign({},e,{value:String(e.value)});let{type:a}=e;a!==O.QUOTE_DOUBLE&&/[\x00-\x08\x0b-\x1f\x7f-\x9f\u{D800}-\u{DFFF}]/u.test(o.value)&&(a=O.QUOTE_DOUBLE);const l=h=>{switch(h){case O.BLOCK_FOLDED:case O.BLOCK_LITERAL:return r||s?kn(o.value,t):Lr(o,t,n,i);case O.QUOTE_DOUBLE:return wi(o.value,t);case O.QUOTE_SINGLE:return ca(o.value,t);case O.PLAIN:return Lm(o,t,n,i);default:return null}};let c=l(a);if(c===null){const{defaultKeyType:h,defaultStringType:u}=t.options,p=r&&h||u;if(c=l(p),c===null)throw new Error(`Unsupported default string type ${p}`)}return c}function pd(e,t){const n=Object.assign({blockQuote:!0,commentString:Im,defaultKeyType:null,defaultStringType:"PLAIN",directives:null,doubleQuotedAsJSON:!1,doubleQuotedMinMultiLineLength:40,falseStr:"false",flowCollectionPadding:!0,indentSeq:!0,lineWidth:80,minContentWidth:20,nullStr:"null",simpleKeys:!1,singleQuote:null,trailingComma:!1,trueStr:"true",verifyAliasOrder:!0},e.schema.toStringOptions,t);let i;switch(n.collectionStyle){case"block":i=!1;break;case"flow":i=!0;break;default:i=null}return{anchors:new Set,doc:e,flowCollectionPadding:n.flowCollectionPadding?" ":"",indent:"",indentStep:typeof n.indent=="number"?" ".repeat(n.indent):"  ",inFlow:i,options:n}}function Dm(e,t){var r;if(t.tag){const s=e.filter(o=>o.tag===t.tag);if(s.length>0)return s.find(o=>o.format===t.format)??s[0]}let n,i;if($(t)){i=t.value;let s=e.filter(o=>{var a;return(a=o.identify)==null?void 0:a.call(o,i)});if(s.length>1){const o=s.filter(a=>a.test);o.length>0&&(s=o)}n=s.find(o=>o.format===t.format)??s.find(o=>!o.format)}else i=t,n=e.find(s=>s.nodeClass&&i instanceof s.nodeClass);if(!n){const s=((r=i==null?void 0:i.constructor)==null?void 0:r.name)??(i===null?"null":typeof i);throw new Error(`Tag not resolved for ${s} value`)}return n}function xm(e,t,{anchors:n,doc:i}){if(!i.directives)return"";const r=[],s=($(e)||Y(e))&&e.anchor;s&&ad(s)&&(n.add(s),r.push(`&${s}`));const o=e.tag??(t.default?null:t.tag);return o&&r.push(i.directives.tagString(o)),r.join(" ")}function Pn(e,t,n,i){var l;if(X(e))return e.toString(t,n,i);if(Hn(e)){if(t.doc.directives)return e.toString(t);if((l=t.resolvedAliases)!=null&&l.has(e))throw new TypeError("Cannot stringify circular structure without alias nodes");t.resolvedAliases?t.resolvedAliases.add(e):t.resolvedAliases=new Set([e]),e=e.resolve(t.doc)}let r;const s=J(e)?e:t.doc.createNode(e,{onTagObj:c=>r=c});r??(r=Dm(t.doc.schema.tags,s));const o=xm(s,r,t);o.length>0&&(t.indentAtStart=(t.indentAtStart??0)+o.length+1);const a=typeof r.stringify=="function"?r.stringify(s,t,n,i):$(s)?ul(s,t,n,i):s.toString(t,n,i);return o?$(s)||a[0]==="{"||a[0]==="["?`${o} ${a}`:`${o}
${t.indent}${a}`:a}function Rm({key:e,value:t},n,i,r){const{allNullValues:s,doc:o,indent:a,indentStep:l,options:{commentString:c,indentSeq:h,simpleKeys:u}}=n;let p=J(e)&&e.comment||null;if(u){if(p)throw new Error("With simple keys, key nodes cannot have comments");if(Y(e)||!J(e)&&typeof e=="object"){const E="With simple keys, collection cannot be used as a key value";throw new Error(E)}}let g=!u&&(!e||p&&t==null&&!n.inFlow||Y(e)||($(e)?e.type===O.BLOCK_FOLDED||e.type===O.BLOCK_LITERAL:typeof e=="object"));n=Object.assign({},n,{allNullValues:!1,implicitKey:!g&&(u||!s),indent:a+l});let v=!1,y=!1,k=Pn(e,n,()=>v=!0,()=>y=!0);if(!g&&!n.inFlow&&k.length>1024){if(u)throw new Error("With simple keys, single line scalar must not span more than 1024 characters");g=!0}if(n.inFlow){if(s||t==null)return v&&i&&i(),k===""?"?":g?`? ${k}`:k}else if(s&&!u||t==null&&g)return k=`? ${k}`,p&&!v?k+=Vt(k,n.indent,c(p)):y&&r&&r(),k;v&&(p=null),g?(p&&(k+=Vt(k,n.indent,c(p))),k=`? ${k}
${a}:`):(k=`${k}:`,p&&(k+=Vt(k,n.indent,c(p))));let d,f,m;J(t)?(d=!!t.spaceBefore,f=t.commentBefore,m=t.comment):(d=!1,f=null,m=null,t&&typeof t=="object"&&(t=o.createNode(t))),n.implicitKey=!1,!g&&!p&&$(t)&&(n.indentAtStart=k.length+1),y=!1,!h&&l.length>=2&&!n.inFlow&&!g&&Ki(t)&&!t.flow&&!t.tag&&!t.anchor&&(n.indent=n.indent.substring(2));let w=!1;const S=Pn(t,n,()=>w=!0,()=>y=!0);let M=" ";if(p||d||f){if(M=d?`
`:"",f){const E=c(f);M+=`
${st(E,n.indent)}`}S===""&&!n.inFlow?M===`
`&&m&&(M=`

`):M+=`
${n.indent}`}else if(!g&&Y(t)){const E=S[0],_=S.indexOf(`
`),I=_!==-1,T=n.inFlow??t.flow??t.items.length===0;if(I||!T){let q=!1;if(I&&(E==="&"||E==="!")){let se=S.indexOf(" ");E==="&"&&se!==-1&&se<_&&S[se+1]==="!"&&(se=S.indexOf(" ",se+1)),(se===-1||_<se)&&(q=!0)}q||(M=`
${n.indent}`)}}else(S===""||S[0]===`
`)&&(M="");return k+=M+S,n.inFlow?w&&i&&i():m&&!w?k+=Vt(k,n.indent,c(m)):y&&r&&r(),k}function hd(e,t){(e==="debug"||e==="warn")&&console.warn(t)}const pr="<<",at={identify:e=>e===pr||typeof e=="symbol"&&e.description===pr,default:"key",tag:"tag:yaml.org,2002:merge",test:/^<<$/,resolve:()=>Object.assign(new O(Symbol(pr)),{addToJSMap:md}),stringify:()=>pr},Pm=(e,t)=>(at.identify(t)||$(t)&&(!t.type||t.type===O.PLAIN)&&at.identify(t.value))&&(e==null?void 0:e.doc.schema.tags.some(n=>n.tag===at.tag&&n.default));function md(e,t,n){const i=gd(e,n);if(Ki(i))for(const r of i.items)ao(e,t,r);else if(Array.isArray(i))for(const r of i)ao(e,t,r);else ao(e,t,i)}function ao(e,t,n){const i=gd(e,n);if(!Ui(i))throw new Error("Merge sources must be maps or map aliases");const r=i.toJSON(null,e,Map);for(const[s,o]of r)t instanceof Map?t.has(s)||t.set(s,o):t instanceof Set?t.add(s):Object.prototype.hasOwnProperty.call(t,s)||Object.defineProperty(t,s,{value:o,writable:!0,enumerable:!0,configurable:!0});return t}function gd(e,t){return e&&Hn(t)?t.resolve(e.doc,e):t}function yd(e,t,{key:n,value:i}){if(J(n)&&n.addToJSMap)n.addToJSMap(e,t,i);else if(Pm(e,n))md(e,t,i);else{const r=Pe(n,"",e);if(t instanceof Map)t.set(r,Pe(i,r,e));else if(t instanceof Set)t.add(r);else{const s=jm(n,r,e),o=Pe(i,s,e);s in t?Object.defineProperty(t,s,{value:o,writable:!0,enumerable:!0,configurable:!0}):t[s]=o}}return t}function jm(e,t,n){if(t===null)return"";if(typeof t!="object")return String(t);if(J(e)&&(n!=null&&n.doc)){const i=pd(n.doc,{});i.anchors=new Set;for(const s of n.anchors.keys())i.anchors.add(s.anchor);i.inFlow=!0,i.inStringifyKey=!0;const r=e.toString(i);if(!n.mapKeyWarned){let s=JSON.stringify(r);s.length>40&&(s=s.substring(0,36)+'..."'),hd(n.doc.options.logLevel,`Keys with collection values will be stringified due to JS Object restrictions: ${s}. Set mapAsMap: true to use object keys.`),n.mapKeyWarned=!0}return r}return JSON.stringify(t)}function fl(e,t,n){const i=ji(e,void 0,n),r=ji(t,void 0,n);return new ye(i,r)}class ye{constructor(t,n=null){Object.defineProperty(this,Fe,{value:sd}),this.key=t,this.value=n}clone(t){let{key:n,value:i}=this;return J(n)&&(n=n.clone(t)),J(i)&&(i=i.clone(t)),new ye(n,i)}toJSON(t,n){const i=n!=null&&n.mapAsMap?new Map:{};return yd(n,i,this)}toString(t,n,i){return t!=null&&t.doc?Rm(this,t,n,i):JSON.stringify(this)}}function vd(e,t,n){return(t.inFlow??e.flow?Fm:$m)(e,t,n)}function $m({comment:e,items:t},n,{blockItemPrefix:i,flowChars:r,itemIndent:s,onChompKeep:o,onComment:a}){const{indent:l,options:{commentString:c}}=n,h=Object.assign({},n,{indent:s,type:null});let u=!1;const p=[];for(let v=0;v<t.length;++v){const y=t[v];let k=null;if(J(y))!u&&y.spaceBefore&&p.push(""),rs(n,p,y.commentBefore,u),y.comment&&(k=y.comment);else if(X(y)){const f=J(y.key)?y.key:null;f&&(!u&&f.spaceBefore&&p.push(""),rs(n,p,f.commentBefore,u))}u=!1;let d=Pn(y,h,()=>k=null,()=>u=!0);k&&(d+=Vt(d,s,c(k))),u&&k&&(u=!1),p.push(i+d)}let g;if(p.length===0)g=r.start+r.end;else{g=p[0];for(let v=1;v<p.length;++v){const y=p[v];g+=y?`
${l}${y}`:`
`}}return e?(g+=`
`+st(c(e),l),a&&a()):u&&o&&o(),g}function Fm({items:e},t,{flowChars:n,itemIndent:i}){const{indent:r,indentStep:s,flowCollectionPadding:o,options:{commentString:a}}=t;i+=s;const l=Object.assign({},t,{indent:i,inFlow:!0,type:null});let c=!1,h=0;const u=[];for(let v=0;v<e.length;++v){const y=e[v];let k=null;if(J(y))y.spaceBefore&&u.push(""),rs(t,u,y.commentBefore,!1),y.comment&&(k=y.comment);else if(X(y)){const f=J(y.key)?y.key:null;f&&(f.spaceBefore&&u.push(""),rs(t,u,f.commentBefore,!1),f.comment&&(c=!0));const m=J(y.value)?y.value:null;m?(m.comment&&(k=m.comment),m.commentBefore&&(c=!0)):y.value==null&&(f!=null&&f.comment)&&(k=f.comment)}k&&(c=!0);let d=Pn(y,l,()=>k=null);c||(c=u.length>h||d.includes(`
`)),v<e.length-1?d+=",":t.options.trailingComma&&(t.options.lineWidth>0&&(c||(c=u.reduce((f,m)=>f+m.length+2,2)+(d.length+2)>t.options.lineWidth)),c&&(d+=",")),k&&(d+=Vt(d,i,a(k))),u.push(d),h=u.length}const{start:p,end:g}=n;if(u.length===0)return p+g;if(!c){const v=u.reduce((y,k)=>y+k.length+2,2);c=t.options.lineWidth>0&&v>t.options.lineWidth}if(c){let v=p;for(const y of u)v+=y?`
${s}${r}${y}`:`
`;return`${v}
${r}${g}`}else return`${p}${o}${u.join(" ")}${o}${g}`}function rs({indent:e,options:{commentString:t}},n,i,r){if(i&&r&&(i=i.replace(/^\n+/,"")),i){const s=st(t(i),e);n.push(s.trimStart())}}function Ut(e,t){const n=$(t)?t.value:t;for(const i of e)if(X(i)&&(i.key===t||i.key===n||$(i.key)&&i.key.value===n))return i}class De extends fd{static get tagName(){return"tag:yaml.org,2002:map"}constructor(t){super(Tt,t),this.items=[]}static from(t,n,i){const{keepUndefined:r,replacer:s}=i,o=new this(t),a=(l,c)=>{if(typeof s=="function")c=s.call(n,l,c);else if(Array.isArray(s)&&!s.includes(l))return;(c!==void 0||r)&&o.items.push(fl(l,c,i))};if(n instanceof Map)for(const[l,c]of n)a(l,c);else if(n&&typeof n=="object")for(const l of Object.keys(n))a(l,n[l]);return typeof t.sortMapEntries=="function"&&o.items.sort(t.sortMapEntries),o}add(t,n){var o;let i;X(t)?i=t:!t||typeof t!="object"||!("key"in t)?i=new ye(t,t==null?void 0:t.value):i=new ye(t.key,t.value);const r=Ut(this.items,i.key),s=(o=this.schema)==null?void 0:o.sortMapEntries;if(r){if(!n)throw new Error(`Key ${i.key} already set`);$(r.value)&&ud(i.value)?r.value.value=i.value:r.value=i.value}else if(s){const a=this.items.findIndex(l=>s(i,l)<0);a===-1?this.items.push(i):this.items.splice(a,0,i)}else this.items.push(i)}delete(t){const n=Ut(this.items,t);return n?this.items.splice(this.items.indexOf(n),1).length>0:!1}get(t,n){const i=Ut(this.items,t),r=i==null?void 0:i.value;return(!n&&$(r)?r.value:r)??void 0}has(t){return!!Ut(this.items,t)}set(t,n){this.add(new ye(t,n),!0)}toJSON(t,n,i){const r=i?new i:n!=null&&n.mapAsMap?new Map:{};n!=null&&n.onCreate&&n.onCreate(r);for(const s of this.items)yd(n,r,s);return r}toString(t,n,i){if(!t)return JSON.stringify(this);for(const r of this.items)if(!X(r))throw new Error(`Map items must all be pairs; found ${JSON.stringify(r)} instead`);return!t.allNullValues&&this.hasAllNullValues(!1)&&(t=Object.assign({},t,{allNullValues:!0})),vd(this,t,{blockItemPrefix:"",flowChars:{start:"{",end:"}"},itemIndent:t.indent||"",onChompKeep:i,onComment:n})}}const Un={collection:"map",default:!0,nodeClass:De,tag:"tag:yaml.org,2002:map",resolve(e,t){return Ui(e)||t("Expected a mapping for this tag"),e},createNode:(e,t,n)=>De.from(e,t,n)};class Zt extends fd{static get tagName(){return"tag:yaml.org,2002:seq"}constructor(t){super(Bn,t),this.items=[]}add(t){this.items.push(t)}delete(t){const n=hr(t);return typeof n!="number"?!1:this.items.splice(n,1).length>0}get(t,n){const i=hr(t);if(typeof i!="number")return;const r=this.items[i];return!n&&$(r)?r.value:r}has(t){const n=hr(t);return typeof n=="number"&&n<this.items.length}set(t,n){const i=hr(t);if(typeof i!="number")throw new Error(`Expected a valid index, not ${t}.`);const r=this.items[i];$(r)&&ud(n)?r.value=n:this.items[i]=n}toJSON(t,n){const i=[];n!=null&&n.onCreate&&n.onCreate(i);let r=0;for(const s of this.items)i.push(Pe(s,String(r++),n));return i}toString(t,n,i){return t?vd(this,t,{blockItemPrefix:"- ",flowChars:{start:"[",end:"]"},itemIndent:(t.indent||"")+"  ",onChompKeep:i,onComment:n}):JSON.stringify(this)}static from(t,n,i){const{replacer:r}=i,s=new this(t);if(n&&Symbol.iterator in Object(n)){let o=0;for(let a of n){if(typeof r=="function"){const l=n instanceof Set?a:String(o++);a=r.call(n,l,a)}s.items.push(ji(a,void 0,i))}}return s}}function hr(e){let t=$(e)?e.value:e;return t&&typeof t=="string"&&(t=Number(t)),typeof t=="number"&&Number.isInteger(t)&&t>=0?t:null}const Kn={collection:"seq",default:!0,nodeClass:Zt,tag:"tag:yaml.org,2002:seq",resolve(e,t){return Ki(e)||t("Expected a sequence for this tag"),e},createNode:(e,t,n)=>Zt.from(e,t,n)},Ms={identify:e=>typeof e=="string",default:!0,tag:"tag:yaml.org,2002:str",resolve:e=>e,stringify(e,t,n,i){return t=Object.assign({actualString:!0},t),ul(e,t,n,i)}},As={identify:e=>e==null,createNode:()=>new O(null),default:!0,tag:"tag:yaml.org,2002:null",test:/^(?:~|[Nn]ull|NULL)?$/,resolve:()=>new O(null),stringify:({source:e},t)=>typeof e=="string"&&As.test.test(e)?e:t.options.nullStr},dl={identify:e=>typeof e=="boolean",default:!0,tag:"tag:yaml.org,2002:bool",test:/^(?:[Tt]rue|TRUE|[Ff]alse|FALSE)$/,resolve:e=>new O(e[0]==="t"||e[0]==="T"),stringify({source:e,value:t},n){if(e&&dl.test.test(e)){const i=e[0]==="t"||e[0]==="T";if(t===i)return e}return t?n.options.trueStr:n.options.falseStr}};function Qe({format:e,minFractionDigits:t,tag:n,value:i}){if(typeof i=="bigint")return String(i);const r=typeof i=="number"?i:Number(i);if(!isFinite(r))return isNaN(r)?".nan":r<0?"-.inf":".inf";let s=Object.is(i,-0)?"-0":JSON.stringify(i);if(!e&&t&&(!n||n==="tag:yaml.org,2002:float")&&/^-?\d/.test(s)&&!s.includes("e")){let o=s.indexOf(".");o<0&&(o=s.length,s+=".");let a=t-(s.length-o-1);for(;a-- >0;)s+="0"}return s}const wd={identify:e=>typeof e=="number",default:!0,tag:"tag:yaml.org,2002:float",test:/^(?:[-+]?\.(?:inf|Inf|INF)|\.nan|\.NaN|\.NAN)$/,resolve:e=>e.slice(-3).toLowerCase()==="nan"?NaN:e[0]==="-"?Number.NEGATIVE_INFINITY:Number.POSITIVE_INFINITY,stringify:Qe},kd={identify:e=>typeof e=="number",default:!0,tag:"tag:yaml.org,2002:float",format:"EXP",test:/^[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)[eE][-+]?[0-9]+$/,resolve:e=>parseFloat(e),stringify(e){const t=Number(e.value);return isFinite(t)?t.toExponential():Qe(e)}},Sd={identify:e=>typeof e=="number",default:!0,tag:"tag:yaml.org,2002:float",test:/^[-+]?(?:\.[0-9]+|[0-9]+\.[0-9]*)$/,resolve(e){const t=new O(parseFloat(e)),n=e.indexOf(".");return n!==-1&&e[e.length-1]==="0"&&(t.minFractionDigits=e.length-n-1),t},stringify:Qe},Ns=e=>typeof e=="bigint"||Number.isInteger(e),pl=(e,t,n,{intAsBigInt:i})=>i?BigInt(e):parseInt(e.substring(t),n);function _d(e,t,n){const{value:i}=e;return Ns(i)&&i>=0?n+i.toString(t):Qe(e)}const bd={identify:e=>Ns(e)&&e>=0,default:!0,tag:"tag:yaml.org,2002:int",format:"OCT",test:/^0o[0-7]+$/,resolve:(e,t,n)=>pl(e,2,8,n),stringify:e=>_d(e,8,"0o")},Ed={identify:Ns,default:!0,tag:"tag:yaml.org,2002:int",test:/^[-+]?[0-9]+$/,resolve:(e,t,n)=>pl(e,0,10,n),stringify:Qe},Cd={identify:e=>Ns(e)&&e>=0,default:!0,tag:"tag:yaml.org,2002:int",format:"HEX",test:/^0x[0-9a-fA-F]+$/,resolve:(e,t,n)=>pl(e,2,16,n),stringify:e=>_d(e,16,"0x")},zm=[Un,Kn,Ms,As,dl,bd,Ed,Cd,wd,kd,Sd];function xc(e){return typeof e=="bigint"||Number.isInteger(e)}const mr=({value:e})=>JSON.stringify(e),Bm=[{identify:e=>typeof e=="string",default:!0,tag:"tag:yaml.org,2002:str",resolve:e=>e,stringify:mr},{identify:e=>e==null,createNode:()=>new O(null),default:!0,tag:"tag:yaml.org,2002:null",test:/^null$/,resolve:()=>null,stringify:mr},{identify:e=>typeof e=="boolean",default:!0,tag:"tag:yaml.org,2002:bool",test:/^true$|^false$/,resolve:e=>e==="true",stringify:mr},{identify:xc,default:!0,tag:"tag:yaml.org,2002:int",test:/^-?(?:0|[1-9][0-9]*)$/,resolve:(e,t,{intAsBigInt:n})=>n?BigInt(e):parseInt(e,10),stringify:({value:e})=>xc(e)?e.toString():JSON.stringify(e)},{identify:e=>typeof e=="number",default:!0,tag:"tag:yaml.org,2002:float",test:/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*)?(?:[eE][-+]?[0-9]+)?$/,resolve:e=>parseFloat(e),stringify:mr}],Hm={default:!0,tag:"",test:/^/,resolve(e,t){return t(`Unresolved plain scalar ${JSON.stringify(e)}`),e}},Vm=[Un,Kn].concat(Bm,Hm),hl={identify:e=>e instanceof Uint8Array,default:!1,tag:"tag:yaml.org,2002:binary",resolve(e,t){if(typeof atob=="function"){const n=atob(e.replace(/[\n\r]/g,"")),i=new Uint8Array(n.length);for(let r=0;r<n.length;++r)i[r]=n.charCodeAt(r);return i}else return t("This environment does not support reading binary tags; either Buffer or atob is required"),e},stringify({comment:e,type:t,value:n},i,r,s){if(!n)return"";const o=n;let a;if(typeof btoa=="function"){let l="";for(let c=0;c<o.length;++c)l+=String.fromCharCode(o[c]);a=btoa(l)}else throw new Error("This environment does not support writing binary tags; either Buffer or btoa is required");if(t??(t=O.BLOCK_LITERAL),t!==O.QUOTE_DOUBLE){const l=Math.max(i.options.lineWidth-i.indent.length,i.options.minContentWidth),c=Math.ceil(a.length/l),h=new Array(c);for(let u=0,p=0;u<c;++u,p+=l)h[u]=a.substr(p,l);a=h.join(t===O.BLOCK_LITERAL?`
`:" ")}return ul({comment:e,type:t,value:a},i,r,s)}};function Md(e,t){if(Ki(e))for(let n=0;n<e.items.length;++n){let i=e.items[n];if(!X(i)){if(Ui(i)){i.items.length>1&&t("Each pair must have its own sequence indicator");const r=i.items[0]||new ye(new O(null));if(i.commentBefore&&(r.key.commentBefore=r.key.commentBefore?`${i.commentBefore}
${r.key.commentBefore}`:i.commentBefore),i.comment){const s=r.value??r.key;s.comment=s.comment?`${i.comment}
${s.comment}`:i.comment}i=r}e.items[n]=X(i)?i:new ye(i)}}else t("Expected a sequence for this tag");return e}function Ad(e,t,n){const{replacer:i}=n,r=new Zt(e);r.tag="tag:yaml.org,2002:pairs";let s=0;if(t&&Symbol.iterator in Object(t))for(let o of t){typeof i=="function"&&(o=i.call(t,String(s++),o));let a,l;if(Array.isArray(o))if(o.length===2)a=o[0],l=o[1];else throw new TypeError(`Expected [key, value] tuple: ${o}`);else if(o&&o instanceof Object){const c=Object.keys(o);if(c.length===1)a=c[0],l=o[a];else throw new TypeError(`Expected tuple with one key, not ${c.length} keys`)}else a=o;r.items.push(fl(a,l,n))}return r}const ml={collection:"seq",default:!1,tag:"tag:yaml.org,2002:pairs",resolve:Md,createNode:Ad};class An extends Zt{constructor(){super(),this.add=De.prototype.add.bind(this),this.delete=De.prototype.delete.bind(this),this.get=De.prototype.get.bind(this),this.has=De.prototype.has.bind(this),this.set=De.prototype.set.bind(this),this.tag=An.tag}toJSON(t,n){if(!n)return super.toJSON(t);const i=new Map;n!=null&&n.onCreate&&n.onCreate(i);for(const r of this.items){let s,o;if(X(r)?(s=Pe(r.key,"",n),o=Pe(r.value,s,n)):s=Pe(r,"",n),i.has(s))throw new Error("Ordered maps must not include duplicate keys");i.set(s,o)}return i}static from(t,n,i){const r=Ad(t,n,i),s=new this;return s.items=r.items,s}}An.tag="tag:yaml.org,2002:omap";const gl={collection:"seq",identify:e=>e instanceof Map,nodeClass:An,default:!1,tag:"tag:yaml.org,2002:omap",resolve(e,t){const n=Md(e,t),i=[];for(const{key:r}of n.items)$(r)&&(i.includes(r.value)?t(`Ordered maps must not include duplicate keys: ${r.value}`):i.push(r.value));return Object.assign(new An,n)},createNode:(e,t,n)=>An.from(e,t,n)};function Nd({value:e,source:t},n){return t&&(e?Td:Id).test.test(t)?t:e?n.options.trueStr:n.options.falseStr}const Td={identify:e=>e===!0,default:!0,tag:"tag:yaml.org,2002:bool",test:/^(?:Y|y|[Yy]es|YES|[Tt]rue|TRUE|[Oo]n|ON)$/,resolve:()=>new O(!0),stringify:Nd},Id={identify:e=>e===!1,default:!0,tag:"tag:yaml.org,2002:bool",test:/^(?:N|n|[Nn]o|NO|[Ff]alse|FALSE|[Oo]ff|OFF)$/,resolve:()=>new O(!1),stringify:Nd},Um={identify:e=>typeof e=="number",default:!0,tag:"tag:yaml.org,2002:float",test:/^(?:[-+]?\.(?:inf|Inf|INF)|\.nan|\.NaN|\.NAN)$/,resolve:e=>e.slice(-3).toLowerCase()==="nan"?NaN:e[0]==="-"?Number.NEGATIVE_INFINITY:Number.POSITIVE_INFINITY,stringify:Qe},Km={identify:e=>typeof e=="number",default:!0,tag:"tag:yaml.org,2002:float",format:"EXP",test:/^[-+]?(?:[0-9][0-9_]*)?(?:\.[0-9_]*)?[eE][-+]?[0-9]+$/,resolve:e=>parseFloat(e.replace(/_/g,"")),stringify(e){const t=Number(e.value);return isFinite(t)?t.toExponential():Qe(e)}},Wm={identify:e=>typeof e=="number",default:!0,tag:"tag:yaml.org,2002:float",test:/^[-+]?(?:[0-9][0-9_]*)?\.[0-9_]*$/,resolve(e){const t=new O(parseFloat(e.replace(/_/g,""))),n=e.indexOf(".");if(n!==-1){const i=e.substring(n+1).replace(/_/g,"");i[i.length-1]==="0"&&(t.minFractionDigits=i.length)}return t},stringify:Qe},Wi=e=>typeof e=="bigint"||Number.isInteger(e);function Ts(e,t,n,{intAsBigInt:i}){const r=e[0];if((r==="-"||r==="+")&&(t+=1),e=e.substring(t).replace(/_/g,""),i){switch(n){case 2:e=`0b${e}`;break;case 8:e=`0o${e}`;break;case 16:e=`0x${e}`;break}const o=BigInt(e);return r==="-"?BigInt(-1)*o:o}const s=parseInt(e,n);return r==="-"?-1*s:s}function yl(e,t,n){const{value:i}=e;if(Wi(i)){const r=i.toString(t);return i<0?"-"+n+r.substr(1):n+r}return Qe(e)}const qm={identify:Wi,default:!0,tag:"tag:yaml.org,2002:int",format:"BIN",test:/^[-+]?0b[0-1_]+$/,resolve:(e,t,n)=>Ts(e,2,2,n),stringify:e=>yl(e,2,"0b")},Qm={identify:Wi,default:!0,tag:"tag:yaml.org,2002:int",format:"OCT",test:/^[-+]?0[0-7_]+$/,resolve:(e,t,n)=>Ts(e,1,8,n),stringify:e=>yl(e,8,"0")},Gm={identify:Wi,default:!0,tag:"tag:yaml.org,2002:int",test:/^[-+]?[0-9][0-9_]*$/,resolve:(e,t,n)=>Ts(e,0,10,n),stringify:Qe},Ym={identify:Wi,default:!0,tag:"tag:yaml.org,2002:int",format:"HEX",test:/^[-+]?0x[0-9a-fA-F_]+$/,resolve:(e,t,n)=>Ts(e,2,16,n),stringify:e=>yl(e,16,"0x")};class Nn extends De{constructor(t){super(t),this.tag=Nn.tag}add(t){let n;X(t)?n=t:t&&typeof t=="object"&&"key"in t&&"value"in t&&t.value===null?n=new ye(t.key,null):n=new ye(t,null),Ut(this.items,n.key)||this.items.push(n)}get(t,n){const i=Ut(this.items,t);return!n&&X(i)?$(i.key)?i.key.value:i.key:i}set(t,n){if(typeof n!="boolean")throw new Error(`Expected boolean value for set(key, value) in a YAML set, not ${typeof n}`);const i=Ut(this.items,t);i&&!n?this.items.splice(this.items.indexOf(i),1):!i&&n&&this.items.push(new ye(t))}toJSON(t,n){return super.toJSON(t,n,Set)}toString(t,n,i){if(!t)return JSON.stringify(this);if(this.hasAllNullValues(!0))return super.toString(Object.assign({},t,{allNullValues:!0}),n,i);throw new Error("Set items must all have null values")}static from(t,n,i){const{replacer:r}=i,s=new this(t);if(n&&Symbol.iterator in Object(n))for(let o of n)typeof r=="function"&&(o=r.call(n,o,o)),s.items.push(fl(o,null,i));return s}}Nn.tag="tag:yaml.org,2002:set";const vl={collection:"map",identify:e=>e instanceof Set,nodeClass:Nn,default:!1,tag:"tag:yaml.org,2002:set",createNode:(e,t,n)=>Nn.from(e,t,n),resolve(e,t){if(Ui(e)){if(e.hasAllNullValues(!0))return Object.assign(new Nn,e);t("Set items must all have null values")}else t("Expected a mapping for this tag");return e}};function wl(e,t){const n=e[0],i=n==="-"||n==="+"?e.substring(1):e,r=o=>t?BigInt(o):Number(o),s=i.replace(/_/g,"").split(":").reduce((o,a)=>o*r(60)+r(a),r(0));return n==="-"?r(-1)*s:s}function Od(e){let{value:t}=e,n=o=>o;if(typeof t=="bigint")n=o=>BigInt(o);else if(isNaN(t)||!isFinite(t))return Qe(e);let i="";t<0&&(i="-",t*=n(-1));const r=n(60),s=[t%r];return t<60?s.unshift(0):(t=(t-s[0])/r,s.unshift(t%r),t>=60&&(t=(t-s[0])/r,s.unshift(t))),i+s.map(o=>String(o).padStart(2,"0")).join(":").replace(/000000\d*$/,"")}const Ld={identify:e=>typeof e=="bigint"||Number.isInteger(e),default:!0,tag:"tag:yaml.org,2002:int",format:"TIME",test:/^[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+$/,resolve:(e,t,{intAsBigInt:n})=>wl(e,n),stringify:Od},Dd={identify:e=>typeof e=="number",default:!0,tag:"tag:yaml.org,2002:float",format:"TIME",test:/^[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*$/,resolve:e=>wl(e,!1),stringify:Od},Is={identify:e=>e instanceof Date,default:!0,tag:"tag:yaml.org,2002:timestamp",test:RegExp("^([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?:(?:t|T|[ \\t]+)([0-9]{1,2}):([0-9]{1,2}):([0-9]{1,2}(\\.[0-9]+)?)(?:[ \\t]*(Z|[-+][012]?[0-9](?::[0-9]{2})?))?)?$"),resolve(e){const t=e.match(Is.test);if(!t)throw new Error("!!timestamp expects a date, starting with yyyy-mm-dd");const[,n,i,r,s,o,a]=t.map(Number),l=t[7]?Number((t[7]+"00").substr(1,3)):0;let c=Date.UTC(n,i-1,r,s||0,o||0,a||0,l);const h=t[8];if(h&&h!=="Z"){let u=wl(h,!1);Math.abs(u)<30&&(u*=60),c-=6e4*u}return new Date(c)},stringify:({value:e})=>(e==null?void 0:e.toISOString().replace(/(T00:00:00)?\.000Z$/,""))??""},Rc=[Un,Kn,Ms,As,Td,Id,qm,Qm,Gm,Ym,Um,Km,Wm,hl,at,gl,ml,vl,Ld,Dd,Is],Pc=new Map([["core",zm],["failsafe",[Un,Kn,Ms]],["json",Vm],["yaml11",Rc],["yaml-1.1",Rc]]),jc={binary:hl,bool:dl,float:Sd,floatExp:kd,floatNaN:wd,floatTime:Dd,int:Ed,intHex:Cd,intOct:bd,intTime:Ld,map:Un,merge:at,null:As,omap:gl,pairs:ml,seq:Kn,set:vl,timestamp:Is},Jm={"tag:yaml.org,2002:binary":hl,"tag:yaml.org,2002:merge":at,"tag:yaml.org,2002:omap":gl,"tag:yaml.org,2002:pairs":ml,"tag:yaml.org,2002:set":vl,"tag:yaml.org,2002:timestamp":Is};function lo(e,t,n){const i=Pc.get(t);if(i&&!e)return n&&!i.includes(at)?i.concat(at):i.slice();let r=i;if(!r)if(Array.isArray(e))r=[];else{const s=Array.from(Pc.keys()).filter(o=>o!=="yaml11").map(o=>JSON.stringify(o)).join(", ");throw new Error(`Unknown schema "${t}"; use one of ${s} or define customTags array`)}if(Array.isArray(e))for(const s of e)r=r.concat(s);else typeof e=="function"&&(r=e(r.slice()));return n&&(r=r.concat(at)),r.reduce((s,o)=>{const a=typeof o=="string"?jc[o]:o;if(!a){const l=JSON.stringify(o),c=Object.keys(jc).map(h=>JSON.stringify(h)).join(", ");throw new Error(`Unknown custom tag ${l}; use one of ${c}`)}return s.includes(a)||s.push(a),s},[])}const Xm=(e,t)=>e.key<t.key?-1:e.key>t.key?1:0;class kl{constructor({compat:t,customTags:n,merge:i,resolveKnownTags:r,schema:s,sortMapEntries:o,toStringDefaults:a}){this.compat=Array.isArray(t)?lo(t,"compat"):t?lo(null,t):null,this.name=typeof s=="string"&&s||"core",this.knownTags=r?Jm:{},this.tags=lo(n,this.name,i),this.toStringOptions=a??null,Object.defineProperty(this,Tt,{value:Un}),Object.defineProperty(this,et,{value:Ms}),Object.defineProperty(this,Bn,{value:Kn}),this.sortMapEntries=typeof o=="function"?o:o===!0?Xm:null}clone(){const t=Object.create(kl.prototype,Object.getOwnPropertyDescriptors(this));return t.tags=this.tags.slice(),t}}function Zm(e,t){var l;const n=[];let i=t.directives===!0;if(t.directives!==!1&&e.directives){const c=e.directives.toString(e);c?(n.push(c),i=!0):e.directives.docStart&&(i=!0)}i&&n.push("---");const r=pd(e,t),{commentString:s}=r.options;if(e.commentBefore){n.length!==1&&n.unshift("");const c=s(e.commentBefore);n.unshift(st(c,""))}let o=!1,a=null;if(e.contents){if(J(e.contents)){if(e.contents.spaceBefore&&i&&n.push(""),e.contents.commentBefore){const u=s(e.contents.commentBefore);n.push(st(u,""))}r.forceBlockIndent=!!e.comment,a=e.contents.comment}const c=a?void 0:()=>o=!0;let h=Pn(e.contents,r,()=>a=null,c);a&&(h+=Vt(h,"",s(a))),(h[0]==="|"||h[0]===">")&&n[n.length-1]==="---"?n[n.length-1]=`--- ${h}`:n.push(h)}else n.push(Pn(e.contents,r));if((l=e.directives)!=null&&l.docEnd)if(e.comment){const c=s(e.comment);c.includes(`
`)?(n.push("..."),n.push(st(c,""))):n.push(`... ${c}`)}else n.push("...");else{let c=e.comment;c&&o&&(c=c.replace(/^\n+/,"")),c&&((!o||a)&&n[n.length-1]!==""&&n.push(""),n.push(st(s(c),"")))}return n.join(`
`)+`
`}class Os{constructor(t,n,i){this.commentBefore=null,this.comment=null,this.errors=[],this.warnings=[],Object.defineProperty(this,Fe,{value:aa});let r=null;typeof n=="function"||Array.isArray(n)?r=n:i===void 0&&n&&(i=n,n=void 0);const s=Object.assign({intAsBigInt:!1,keepSourceTokens:!1,logLevel:"warn",prettyErrors:!0,strict:!0,stringKeys:!1,uniqueKeys:!0,version:"1.2"},i);this.options=s;let{version:o}=s;i!=null&&i._directives?(this.directives=i._directives.atDocument(),this.directives.yaml.explicit&&(o=this.directives.yaml.version)):this.directives=new me({version:o}),this.setSchema(o,i),this.contents=t===void 0?null:this.createNode(t,r,i)}clone(){const t=Object.create(Os.prototype,{[Fe]:{value:aa}});return t.commentBefore=this.commentBefore,t.comment=this.comment,t.errors=this.errors.slice(),t.warnings=this.warnings.slice(),t.options=Object.assign({},this.options),this.directives&&(t.directives=this.directives.clone()),t.schema=this.schema.clone(),t.contents=J(this.contents)?this.contents.clone(t.schema):this.contents,this.range&&(t.range=this.range.slice()),t}add(t){rn(this.contents)&&this.contents.add(t)}addIn(t,n){rn(this.contents)&&this.contents.addIn(t,n)}createAlias(t,n){if(!t.anchor){const i=ld(this);t.anchor=!n||i.has(n)?cd(n||"a",i):n}return new cl(t.anchor)}createNode(t,n,i){let r;if(typeof n=="function")t=n.call({"":t},"",t),r=n;else if(Array.isArray(n)){const k=f=>typeof f=="number"||f instanceof String||f instanceof Number,d=n.filter(k).map(String);d.length>0&&(n=n.concat(d)),r=n}else i===void 0&&n&&(i=n,n=void 0);const{aliasDuplicateObjects:s,anchorPrefix:o,flow:a,keepUndefined:l,onTagObj:c,tag:h}=i??{},{onAnchor:u,setAnchors:p,sourceObjects:g}=Am(this,o||"a"),v={aliasDuplicateObjects:s??!0,keepUndefined:l??!1,onAnchor:u,onTagObj:c,replacer:r,schema:this.schema,sourceObjects:g},y=ji(t,h,v);return a&&Y(y)&&(y.flow=!0),p(),y}createPair(t,n,i={}){const r=this.createNode(t,null,i),s=this.createNode(n,null,i);return new ye(r,s)}delete(t){return rn(this.contents)?this.contents.delete(t):!1}deleteIn(t){return oi(t)?this.contents==null?!1:(this.contents=null,!0):rn(this.contents)?this.contents.deleteIn(t):!1}get(t,n){return Y(this.contents)?this.contents.get(t,n):void 0}getIn(t,n){return oi(t)?!n&&$(this.contents)?this.contents.value:this.contents:Y(this.contents)?this.contents.getIn(t,n):void 0}has(t){return Y(this.contents)?this.contents.has(t):!1}hasIn(t){return oi(t)?this.contents!==void 0:Y(this.contents)?this.contents.hasIn(t):!1}set(t,n){this.contents==null?this.contents=is(this.schema,[t],n):rn(this.contents)&&this.contents.set(t,n)}setIn(t,n){oi(t)?this.contents=n:this.contents==null?this.contents=is(this.schema,Array.from(t),n):rn(this.contents)&&this.contents.setIn(t,n)}setSchema(t,n={}){typeof t=="number"&&(t=String(t));let i;switch(t){case"1.1":this.directives?this.directives.yaml.version="1.1":this.directives=new me({version:"1.1"}),i={resolveKnownTags:!1,schema:"yaml-1.1"};break;case"1.2":case"next":this.directives?this.directives.yaml.version=t:this.directives=new me({version:t}),i={resolveKnownTags:!0,schema:"core"};break;case null:this.directives&&delete this.directives,i=null;break;default:{const r=JSON.stringify(t);throw new Error(`Expected '1.1', '1.2' or null as first argument, but found: ${r}`)}}if(n.schema instanceof Object)this.schema=n.schema;else if(i)this.schema=new kl(Object.assign(i,n));else throw new Error("With a null YAML version, the { schema: Schema } option is required")}toJS({json:t,jsonArg:n,mapAsMap:i,maxAliasCount:r,onAnchor:s,reviver:o}={}){const a={anchors:new Map,doc:this,keep:!t,mapAsMap:i===!0,mapKeyWarned:!1,maxAliasCount:typeof r=="number"?r:100},l=Pe(this.contents,n??"",a);if(typeof s=="function")for(const{count:c,res:h}of a.anchors.values())s(h,c);return typeof o=="function"?wn(o,{"":l},"",l):l}toJSON(t,n){return this.toJS({json:!0,jsonArg:t,mapAsMap:!1,onAnchor:n})}toString(t={}){if(this.errors.length>0)throw new Error("Document with errors cannot be stringified");if("indent"in t&&(!Number.isInteger(t.indent)||Number(t.indent)<=0)){const n=JSON.stringify(t.indent);throw new Error(`"indent" option must be a positive integer, not ${n}`)}return Zm(this,t)}}function rn(e){if(Y(e))return!0;throw new Error("Expected a YAML collection as document contents")}class xd extends Error{constructor(t,n,i,r){super(),this.name=t,this.code=i,this.message=r,this.pos=n}}class ai extends xd{constructor(t,n,i){super("YAMLParseError",t,n,i)}}class eg extends xd{constructor(t,n,i){super("YAMLWarning",t,n,i)}}const $c=(e,t)=>n=>{if(n.pos[0]===-1)return;n.linePos=n.pos.map(a=>t.linePos(a));const{line:i,col:r}=n.linePos[0];n.message+=` at line ${i}, column ${r}`;let s=r-1,o=e.substring(t.lineStarts[i-1],t.lineStarts[i]).replace(/[\n\r]+$/,"");if(s>=60&&o.length>80){const a=Math.min(s-39,o.length-79);o="…"+o.substring(a),s-=a-1}if(o.length>80&&(o=o.substring(0,79)+"…"),i>1&&/^ *$/.test(o.substring(0,s))){let a=e.substring(t.lineStarts[i-2],t.lineStarts[i-1]);a.length>80&&(a=a.substring(0,79)+`…
`),o=a+o}if(/[^ ]/.test(o)){let a=1;const l=n.linePos[1];(l==null?void 0:l.line)===i&&l.col>r&&(a=Math.max(1,Math.min(l.col-r,80-s)));const c=" ".repeat(s)+"^".repeat(a);n.message+=`:

${o}
${c}
`}};function jn(e,{flow:t,indicator:n,next:i,offset:r,onError:s,parentIndent:o,startOnNewline:a}){let l=!1,c=a,h=a,u="",p="",g=!1,v=!1,y=null,k=null,d=null,f=null,m=null,w=null,S=null;for(const _ of e)switch(v&&(_.type!=="space"&&_.type!=="newline"&&_.type!=="comma"&&s(_.offset,"MISSING_CHAR","Tags and anchors must be separated from the next token by white space"),v=!1),y&&(c&&_.type!=="comment"&&_.type!=="newline"&&s(y,"TAB_AS_INDENT","Tabs are not allowed as indentation"),y=null),_.type){case"space":!t&&(n!=="doc-start"||(i==null?void 0:i.type)!=="flow-collection")&&_.source.includes("	")&&(y=_),h=!0;break;case"comment":{h||s(_,"MISSING_CHAR","Comments must be separated from other tokens by white space characters");const I=_.source.substring(1)||" ";u?u+=p+I:u=I,p="",c=!1;break}case"newline":c?u?u+=_.source:(!w||n!=="seq-item-ind")&&(l=!0):p+=_.source,c=!0,g=!0,(k||d)&&(f=_),h=!0;break;case"anchor":k&&s(_,"MULTIPLE_ANCHORS","A node can have at most one anchor"),_.source.endsWith(":")&&s(_.offset+_.source.length-1,"BAD_ALIAS","Anchor ending in : is ambiguous",!0),k=_,S??(S=_.offset),c=!1,h=!1,v=!0;break;case"tag":{d&&s(_,"MULTIPLE_TAGS","A node can have at most one tag"),d=_,S??(S=_.offset),c=!1,h=!1,v=!0;break}case n:(k||d)&&s(_,"BAD_PROP_ORDER",`Anchors and tags must be after the ${_.source} indicator`),w&&s(_,"UNEXPECTED_TOKEN",`Unexpected ${_.source} in ${t??"collection"}`),w=_,c=n==="seq-item-ind"||n==="explicit-key-ind",h=!1;break;case"comma":if(t){m&&s(_,"UNEXPECTED_TOKEN",`Unexpected , in ${t}`),m=_,c=!1,h=!1;break}default:s(_,"UNEXPECTED_TOKEN",`Unexpected ${_.type} token`),c=!1,h=!1}const M=e[e.length-1],E=M?M.offset+M.source.length:r;return v&&i&&i.type!=="space"&&i.type!=="newline"&&i.type!=="comma"&&(i.type!=="scalar"||i.source!=="")&&s(i.offset,"MISSING_CHAR","Tags and anchors must be separated from the next token by white space"),y&&(c&&y.indent<=o||(i==null?void 0:i.type)==="block-map"||(i==null?void 0:i.type)==="block-seq")&&s(y,"TAB_AS_INDENT","Tabs are not allowed as indentation"),{comma:m,found:w,spaceBefore:l,comment:u,hasNewline:g,anchor:k,tag:d,newlineAfterProp:f,end:E,start:S??E}}function $i(e){if(!e)return null;switch(e.type){case"alias":case"scalar":case"double-quoted-scalar":case"single-quoted-scalar":if(e.source.includes(`
`))return!0;if(e.end){for(const t of e.end)if(t.type==="newline")return!0}return!1;case"flow-collection":for(const t of e.items){for(const n of t.start)if(n.type==="newline")return!0;if(t.sep){for(const n of t.sep)if(n.type==="newline")return!0}if($i(t.key)||$i(t.value))return!0}return!1;default:return!0}}function fa(e,t,n){if((t==null?void 0:t.type)==="flow-collection"){const i=t.end[0];i.indent===e&&(i.source==="]"||i.source==="}")&&$i(t)&&n(i,"BAD_INDENT","Flow end indicator should be more indented than parent",!0)}}function Rd(e,t,n){const{uniqueKeys:i}=e.options;if(i===!1)return!1;const r=typeof i=="function"?i:(s,o)=>s===o||$(s)&&$(o)&&s.value===o.value;return t.some(s=>r(s.key,n))}const Fc="All mapping items must start at the same column";function tg({composeNode:e,composeEmptyNode:t},n,i,r,s){var h;const o=(s==null?void 0:s.nodeClass)??De,a=new o(n.schema);n.atRoot&&(n.atRoot=!1);let l=i.offset,c=null;for(const u of i.items){const{start:p,key:g,sep:v,value:y}=u,k=jn(p,{indicator:"explicit-key-ind",next:g??(v==null?void 0:v[0]),offset:l,onError:r,parentIndent:i.indent,startOnNewline:!0}),d=!k.found;if(d){if(g&&(g.type==="block-seq"?r(l,"BLOCK_AS_IMPLICIT_KEY","A block sequence may not be used as an implicit map key"):"indent"in g&&g.indent!==i.indent&&r(l,"BAD_INDENT",Fc)),!k.anchor&&!k.tag&&!v){c=k.end,k.comment&&(a.comment?a.comment+=`
`+k.comment:a.comment=k.comment);continue}(k.newlineAfterProp||$i(g))&&r(g??p[p.length-1],"MULTILINE_IMPLICIT_KEY","Implicit keys need to be on a single line")}else((h=k.found)==null?void 0:h.indent)!==i.indent&&r(l,"BAD_INDENT",Fc);n.atKey=!0;const f=k.end,m=g?e(n,g,k,r):t(n,f,p,null,k,r);n.schema.compat&&fa(i.indent,g,r),n.atKey=!1,Rd(n,a.items,m)&&r(f,"DUPLICATE_KEY","Map keys must be unique");const w=jn(v??[],{indicator:"map-value-ind",next:y,offset:m.range[2],onError:r,parentIndent:i.indent,startOnNewline:!g||g.type==="block-scalar"});if(l=w.end,w.found){d&&((y==null?void 0:y.type)==="block-map"&&!w.hasNewline&&r(l,"BLOCK_AS_IMPLICIT_KEY","Nested mappings are not allowed in compact mappings"),n.options.strict&&k.start<w.found.offset-1024&&r(m.range,"KEY_OVER_1024_CHARS","The : indicator must be at most 1024 chars after the start of an implicit block mapping key"));const S=y?e(n,y,w,r):t(n,l,v,null,w,r);n.schema.compat&&fa(i.indent,y,r),l=S.range[2];const M=new ye(m,S);n.options.keepSourceTokens&&(M.srcToken=u),a.items.push(M)}else{d&&r(m.range,"MISSING_CHAR","Implicit map keys need to be followed by map values"),w.comment&&(m.comment?m.comment+=`
`+w.comment:m.comment=w.comment);const S=new ye(m);n.options.keepSourceTokens&&(S.srcToken=u),a.items.push(S)}}return c&&c<l&&r(c,"IMPOSSIBLE","Map comment with trailing content"),a.range=[i.offset,l,c??l],a}function ng({composeNode:e,composeEmptyNode:t},n,i,r,s){const o=(s==null?void 0:s.nodeClass)??Zt,a=new o(n.schema);n.atRoot&&(n.atRoot=!1),n.atKey&&(n.atKey=!1);let l=i.offset,c=null;for(const{start:h,value:u}of i.items){const p=jn(h,{indicator:"seq-item-ind",next:u,offset:l,onError:r,parentIndent:i.indent,startOnNewline:!0});if(!p.found)if(p.anchor||p.tag||u)(u==null?void 0:u.type)==="block-seq"?r(p.end,"BAD_INDENT","All sequence items must start at the same column"):r(l,"MISSING_CHAR","Sequence item without - indicator");else{c=p.end,p.comment&&(a.comment=p.comment);continue}const g=u?e(n,u,p,r):t(n,p.end,h,null,p,r);n.schema.compat&&fa(i.indent,u,r),l=g.range[2],a.items.push(g)}return a.range=[i.offset,l,c??l],a}function qi(e,t,n,i){let r="";if(e){let s=!1,o="";for(const a of e){const{source:l,type:c}=a;switch(c){case"space":s=!0;break;case"comment":{n&&!s&&i(a,"MISSING_CHAR","Comments must be separated from other tokens by white space characters");const h=l.substring(1)||" ";r?r+=o+h:r=h,o="";break}case"newline":r&&(o+=l),s=!0;break;default:i(a,"UNEXPECTED_TOKEN",`Unexpected ${c} at node end`)}t+=l.length}}return{comment:r,offset:t}}const co="Block collections are not allowed within flow collections",uo=e=>e&&(e.type==="block-map"||e.type==="block-seq");function ig({composeNode:e,composeEmptyNode:t},n,i,r,s){var k;const o=i.start.source==="{",a=o?"flow map":"flow sequence",l=(s==null?void 0:s.nodeClass)??(o?De:Zt),c=new l(n.schema);c.flow=!0;const h=n.atRoot;h&&(n.atRoot=!1),n.atKey&&(n.atKey=!1);let u=i.offset+i.start.source.length;for(let d=0;d<i.items.length;++d){const f=i.items[d],{start:m,key:w,sep:S,value:M}=f,E=jn(m,{flow:a,indicator:"explicit-key-ind",next:w??(S==null?void 0:S[0]),offset:u,onError:r,parentIndent:i.indent,startOnNewline:!1});if(!E.found){if(!E.anchor&&!E.tag&&!S&&!M){d===0&&E.comma?r(E.comma,"UNEXPECTED_TOKEN",`Unexpected , in ${a}`):d<i.items.length-1&&r(E.start,"UNEXPECTED_TOKEN",`Unexpected empty item in ${a}`),E.comment&&(c.comment?c.comment+=`
`+E.comment:c.comment=E.comment),u=E.end;continue}!o&&n.options.strict&&$i(w)&&r(w,"MULTILINE_IMPLICIT_KEY","Implicit keys of flow sequence pairs need to be on a single line")}if(d===0)E.comma&&r(E.comma,"UNEXPECTED_TOKEN",`Unexpected , in ${a}`);else if(E.comma||r(E.start,"MISSING_CHAR",`Missing , between ${a} items`),E.comment){let _="";e:for(const I of m)switch(I.type){case"comma":case"space":break;case"comment":_=I.source.substring(1);break e;default:break e}if(_){let I=c.items[c.items.length-1];X(I)&&(I=I.value??I.key),I.comment?I.comment+=`
`+_:I.comment=_,E.comment=E.comment.substring(_.length+1)}}if(!o&&!S&&!E.found){const _=M?e(n,M,E,r):t(n,E.end,S,null,E,r);c.items.push(_),u=_.range[2],uo(M)&&r(_.range,"BLOCK_IN_FLOW",co)}else{n.atKey=!0;const _=E.end,I=w?e(n,w,E,r):t(n,_,m,null,E,r);uo(w)&&r(I.range,"BLOCK_IN_FLOW",co),n.atKey=!1;const T=jn(S??[],{flow:a,indicator:"map-value-ind",next:M,offset:I.range[2],onError:r,parentIndent:i.indent,startOnNewline:!1});if(T.found){if(!o&&!E.found&&n.options.strict){if(S)for(const oe of S){if(oe===T.found)break;if(oe.type==="newline"){r(oe,"MULTILINE_IMPLICIT_KEY","Implicit keys of flow sequence pairs need to be on a single line");break}}E.start<T.found.offset-1024&&r(T.found,"KEY_OVER_1024_CHARS","The : indicator must be at most 1024 chars after the start of an implicit flow sequence key")}}else M&&("source"in M&&((k=M.source)==null?void 0:k[0])===":"?r(M,"MISSING_CHAR",`Missing space after : in ${a}`):r(T.start,"MISSING_CHAR",`Missing , or : between ${a} items`));const q=M?e(n,M,T,r):T.found?t(n,T.end,S,null,T,r):null;q?uo(M)&&r(q.range,"BLOCK_IN_FLOW",co):T.comment&&(I.comment?I.comment+=`
`+T.comment:I.comment=T.comment);const se=new ye(I,q);if(n.options.keepSourceTokens&&(se.srcToken=f),o){const oe=c;Rd(n,oe.items,I)&&r(_,"DUPLICATE_KEY","Map keys must be unique"),oe.items.push(se)}else{const oe=new De(n.schema);oe.flow=!0,oe.items.push(se);const Wn=(q??I).range;oe.range=[I.range[0],Wn[1],Wn[2]],c.items.push(oe)}u=q?q.range[2]:T.end}}const p=o?"}":"]",[g,...v]=i.end;let y=u;if((g==null?void 0:g.source)===p)y=g.offset+g.source.length;else{const d=a[0].toUpperCase()+a.substring(1),f=h?`${d} must end with a ${p}`:`${d} in block collection must be sufficiently indented and end with a ${p}`;r(u,h?"MISSING_CHAR":"BAD_INDENT",f),g&&g.source.length!==1&&v.unshift(g)}if(v.length>0){const d=qi(v,y,n.options.strict,r);d.comment&&(c.comment?c.comment+=`
`+d.comment:c.comment=d.comment),c.range=[i.offset,y,d.offset]}else c.range=[i.offset,y,y];return c}function fo(e,t,n,i,r,s){const o=n.type==="block-map"?tg(e,t,n,i,s):n.type==="block-seq"?ng(e,t,n,i,s):ig(e,t,n,i,s),a=o.constructor;return r==="!"||r===a.tagName?(o.tag=a.tagName,o):(r&&(o.tag=r),o)}function rg(e,t,n,i,r){var p;const s=i.tag,o=s?t.directives.tagName(s.source,g=>r(s,"TAG_RESOLVE_FAILED",g)):null;if(n.type==="block-seq"){const{anchor:g,newlineAfterProp:v}=i,y=g&&s?g.offset>s.offset?g:s:g??s;y&&(!v||v.offset<y.offset)&&r(y,"MISSING_CHAR","Missing newline after block sequence props")}const a=n.type==="block-map"?"map":n.type==="block-seq"?"seq":n.start.source==="{"?"map":"seq";if(!s||!o||o==="!"||o===De.tagName&&a==="map"||o===Zt.tagName&&a==="seq")return fo(e,t,n,r,o);let l=t.schema.tags.find(g=>g.tag===o&&g.collection===a);if(!l){const g=t.schema.knownTags[o];if((g==null?void 0:g.collection)===a)t.schema.tags.push(Object.assign({},g,{default:!1})),l=g;else return g?r(s,"BAD_COLLECTION_TYPE",`${g.tag} used for ${a} collection, but expects ${g.collection??"scalar"}`,!0):r(s,"TAG_RESOLVE_FAILED",`Unresolved tag: ${o}`,!0),fo(e,t,n,r,o)}const c=fo(e,t,n,r,o,l),h=((p=l.resolve)==null?void 0:p.call(l,c,g=>r(s,"TAG_RESOLVE_FAILED",g),t.options))??c,u=J(h)?h:new O(h);return u.range=c.range,u.tag=o,l!=null&&l.format&&(u.format=l.format),u}function sg(e,t,n){const i=t.offset,r=og(t,e.options.strict,n);if(!r)return{value:"",type:null,comment:"",range:[i,i,i]};const s=r.mode===">"?O.BLOCK_FOLDED:O.BLOCK_LITERAL,o=t.source?ag(t.source):[];let a=o.length;for(let y=o.length-1;y>=0;--y){const k=o[y][1];if(k===""||k==="\r")a=y;else break}if(a===0){const y=r.chomp==="+"&&o.length>0?`
`.repeat(Math.max(1,o.length-1)):"";let k=i+r.length;return t.source&&(k+=t.source.length),{value:y,type:s,comment:r.comment,range:[i,k,k]}}let l=t.indent+r.indent,c=t.offset+r.length,h=0;for(let y=0;y<a;++y){const[k,d]=o[y];if(d===""||d==="\r")r.indent===0&&k.length>l&&(l=k.length);else{k.length<l&&n(c+k.length,"MISSING_CHAR","Block scalars with more-indented leading empty lines must use an explicit indentation indicator"),r.indent===0&&(l=k.length),h=y,l===0&&!e.atRoot&&n(c,"BAD_INDENT","Block scalar values in collections must be indented");break}c+=k.length+d.length+1}for(let y=o.length-1;y>=a;--y)o[y][0].length>l&&(a=y+1);let u="",p="",g=!1;for(let y=0;y<h;++y)u+=o[y][0].slice(l)+`
`;for(let y=h;y<a;++y){let[k,d]=o[y];c+=k.length+d.length+1;const f=d[d.length-1]==="\r";if(f&&(d=d.slice(0,-1)),d&&k.length<l){const w=`Block scalar lines must not be less indented than their ${r.indent?"explicit indentation indicator":"first line"}`;n(c-d.length-(f?2:1),"BAD_INDENT",w),k=""}s===O.BLOCK_LITERAL?(u+=p+k.slice(l)+d,p=`
`):k.length>l||d[0]==="	"?(p===" "?p=`
`:!g&&p===`
`&&(p=`

`),u+=p+k.slice(l)+d,p=`
`,g=!0):d===""?p===`
`?u+=`
`:p=`
`:(u+=p+d,p=" ",g=!1)}switch(r.chomp){case"-":break;case"+":for(let y=a;y<o.length;++y)u+=`
`+o[y][0].slice(l);u[u.length-1]!==`
`&&(u+=`
`);break;default:u+=`
`}const v=i+r.length+t.source.length;return{value:u,type:s,comment:r.comment,range:[i,v,v]}}function og({offset:e,props:t},n,i){if(t[0].type!=="block-scalar-header")return i(t[0],"IMPOSSIBLE","Block scalar header not found"),null;const{source:r}=t[0],s=r[0];let o=0,a="",l=-1;for(let p=1;p<r.length;++p){const g=r[p];if(!a&&(g==="-"||g==="+"))a=g;else{const v=Number(g);!o&&v?o=v:l===-1&&(l=e+p)}}l!==-1&&i(l,"UNEXPECTED_TOKEN",`Block scalar header includes extra characters: ${r}`);let c=!1,h="",u=r.length;for(let p=1;p<t.length;++p){const g=t[p];switch(g.type){case"space":c=!0;case"newline":u+=g.source.length;break;case"comment":n&&!c&&i(g,"MISSING_CHAR","Comments must be separated from other tokens by white space characters"),u+=g.source.length,h=g.source.substring(1);break;case"error":i(g,"UNEXPECTED_TOKEN",g.message),u+=g.source.length;break;default:{const v=`Unexpected token in block scalar header: ${g.type}`;i(g,"UNEXPECTED_TOKEN",v);const y=g.source;y&&typeof y=="string"&&(u+=y.length)}}}return{mode:s,indent:o,chomp:a,comment:h,length:u}}function ag(e){const t=e.split(/\n( *)/),n=t[0],i=n.match(/^( *)/),s=[i!=null&&i[1]?[i[1],n.slice(i[1].length)]:["",n]];for(let o=1;o<t.length;o+=2)s.push([t[o],t[o+1]]);return s}function lg(e,t,n){const{offset:i,type:r,source:s,end:o}=e;let a,l;const c=(p,g,v)=>n(i+p,g,v);switch(r){case"scalar":a=O.PLAIN,l=cg(s,c);break;case"single-quoted-scalar":a=O.QUOTE_SINGLE,l=ug(s,c);break;case"double-quoted-scalar":a=O.QUOTE_DOUBLE,l=fg(s,c);break;default:return n(e,"UNEXPECTED_TOKEN",`Expected a flow scalar value, but found: ${r}`),{value:"",type:null,comment:"",range:[i,i+s.length,i+s.length]}}const h=i+s.length,u=qi(o,h,t,n);return{value:l,type:a,comment:u.comment,range:[i,h,u.offset]}}function cg(e,t){let n="";switch(e[0]){case"	":n="a tab character";break;case",":n="flow indicator character ,";break;case"%":n="directive indicator character %";break;case"|":case">":{n=`block scalar indicator ${e[0]}`;break}case"@":case"`":{n=`reserved character ${e[0]}`;break}}return n&&t(0,"BAD_SCALAR_START",`Plain value cannot start with ${n}`),Pd(e)}function ug(e,t){return(e[e.length-1]!=="'"||e.length===1)&&t(e.length,"MISSING_CHAR","Missing closing 'quote"),Pd(e.slice(1,-1)).replace(/''/g,"'")}function Pd(e){const t=/(.*?)\r?\n/sy;let n=t.exec(e);if(!n)return e;let i,r;try{i=new RegExp("(?<![ 	])[ 	]+$"),r=new RegExp("^[ 	]+|(?<![ 	])[ 	]+$","g")}catch{i=/[ \t]+$/,r=/^[ \t]+|[ \t]+$/g}let s=n[1].replace(i,""),o=" ",a=t.lastIndex;for(;n=t.exec(e);){const c=n[1].replace(r,"");c===""?o===`
`?s+=o:o=`
`:(s+=o+c,o=" "),a=t.lastIndex}const l=/[ \t]*(.*)/sy;return l.lastIndex=a,n=l.exec(e),s+o+((n==null?void 0:n[1])??"")}function fg(e,t){let n="";for(let i=1;i<e.length-1;++i){const r=e[i];if(!(r==="\r"&&e[i+1]===`
`))if(r===`
`){const{fold:s,offset:o}=dg(e,i);n+=s,i=o}else if(r==="\\"){let s=e[++i];const o=pg[s];if(o)n+=o;else if(s===`
`)for(s=e[i+1];s===" "||s==="	";)s=e[++i+1];else if(s==="\r"&&e[i+1]===`
`)for(s=e[++i+1];s===" "||s==="	";)s=e[++i+1];else if(s==="x"||s==="u"||s==="U"){const a=s==="x"?2:s==="u"?4:8;n+=hg(e,i+1,a,t),i+=a}else{const a=e.substr(i-1,2);t(i-1,"BAD_DQ_ESCAPE",`Invalid escape sequence ${a}`),n+=a}}else if(r===" "||r==="	"){const s=i;let o=e[i+1];for(;o===" "||o==="	";)o=e[++i+1];o!==`
`&&!(o==="\r"&&e[i+2]===`
`)&&(n+=i>s?e.slice(s,i+1):r)}else n+=r}return(e[e.length-1]!=='"'||e.length===1)&&t(e.length,"MISSING_CHAR",'Missing closing "quote'),n}function dg(e,t){let n="",i=e[t+1];for(;(i===" "||i==="	"||i===`
`||i==="\r")&&!(i==="\r"&&e[t+2]!==`
`);)i===`
`&&(n+=`
`),t+=1,i=e[t+1];return n||(n=" "),{fold:n,offset:t}}const pg={0:"\0",a:"\x07",b:"\b",e:"\x1B",f:"\f",n:`
`,r:"\r",t:"	",v:"\v",N:"",_:" ",L:"\u2028",P:"\u2029"," ":" ",'"':'"',"/":"/","\\":"\\","	":"	"};function hg(e,t,n,i){const r=e.substr(t,n),o=r.length===n&&/^[0-9a-fA-F]+$/.test(r)?parseInt(r,16):NaN;try{return String.fromCodePoint(o)}catch{const a=e.substr(t-2,n+2);return i(t-2,"BAD_DQ_ESCAPE",`Invalid escape sequence ${a}`),a}}function jd(e,t,n,i){const{value:r,type:s,comment:o,range:a}=t.type==="block-scalar"?sg(e,t,i):lg(t,e.options.strict,i),l=n?e.directives.tagName(n.source,u=>i(n,"TAG_RESOLVE_FAILED",u)):null;let c;e.options.stringKeys&&e.atKey?c=e.schema[et]:l?c=mg(e.schema,r,l,n,i):t.type==="scalar"?c=gg(e,r,t,i):c=e.schema[et];let h;try{const u=c.resolve(r,p=>i(n??t,"TAG_RESOLVE_FAILED",p),e.options);h=$(u)?u:new O(u)}catch(u){const p=u instanceof Error?u.message:String(u);i(n??t,"TAG_RESOLVE_FAILED",p),h=new O(r)}return h.range=a,h.source=r,s&&(h.type=s),l&&(h.tag=l),c.format&&(h.format=c.format),o&&(h.comment=o),h}function mg(e,t,n,i,r){var a;if(n==="!")return e[et];const s=[];for(const l of e.tags)if(!l.collection&&l.tag===n)if(l.default&&l.test)s.push(l);else return l;for(const l of s)if((a=l.test)!=null&&a.test(t))return l;const o=e.knownTags[n];return o&&!o.collection?(e.tags.push(Object.assign({},o,{default:!1,test:void 0})),o):(r(i,"TAG_RESOLVE_FAILED",`Unresolved tag: ${n}`,n!=="tag:yaml.org,2002:str"),e[et])}function gg({atKey:e,directives:t,schema:n},i,r,s){const o=n.tags.find(a=>{var l;return(a.default===!0||e&&a.default==="key")&&((l=a.test)==null?void 0:l.test(i))})||n[et];if(n.compat){const a=n.compat.find(l=>{var c;return l.default&&((c=l.test)==null?void 0:c.test(i))})??n[et];if(o.tag!==a.tag){const l=t.tagString(o.tag),c=t.tagString(a.tag),h=`Value may be parsed as either ${l} or ${c}`;s(r,"TAG_RESOLVE_FAILED",h,!0)}}return o}function yg(e,t,n){if(t){n??(n=t.length);for(let i=n-1;i>=0;--i){let r=t[i];switch(r.type){case"space":case"comment":case"newline":e-=r.source.length;continue}for(r=t[++i];(r==null?void 0:r.type)==="space";)e+=r.source.length,r=t[++i];break}}return e}const vg={composeNode:$d,composeEmptyNode:Sl};function $d(e,t,n,i){const r=e.atKey,{spaceBefore:s,comment:o,anchor:a,tag:l}=n;let c,h=!0;switch(t.type){case"alias":c=wg(e,t,i),(a||l)&&i(t,"ALIAS_PROPS","An alias node must not specify any properties");break;case"scalar":case"single-quoted-scalar":case"double-quoted-scalar":case"block-scalar":c=jd(e,t,l,i),a&&(c.anchor=a.source.substring(1));break;case"block-map":case"block-seq":case"flow-collection":try{c=rg(vg,e,t,n,i),a&&(c.anchor=a.source.substring(1))}catch(u){const p=u instanceof Error?u.message:String(u);i(t,"RESOURCE_EXHAUSTION",p)}break;default:{const u=t.type==="error"?t.message:`Unsupported token (type: ${t.type})`;i(t,"UNEXPECTED_TOKEN",u),h=!1}}return c??(c=Sl(e,t.offset,void 0,null,n,i)),a&&c.anchor===""&&i(a,"BAD_ALIAS","Anchor cannot be an empty string"),r&&e.options.stringKeys&&(!$(c)||typeof c.value!="string"||c.tag&&c.tag!=="tag:yaml.org,2002:str")&&i(l??t,"NON_STRING_KEY","With stringKeys, all keys must be strings"),s&&(c.spaceBefore=!0),o&&(t.type==="scalar"&&t.source===""?c.comment=o:c.commentBefore=o),e.options.keepSourceTokens&&h&&(c.srcToken=t),c}function Sl(e,t,n,i,{spaceBefore:r,comment:s,anchor:o,tag:a,end:l},c){const h={type:"scalar",offset:yg(t,n,i),indent:-1,source:""},u=jd(e,h,a,c);return o&&(u.anchor=o.source.substring(1),u.anchor===""&&c(o,"BAD_ALIAS","Anchor cannot be an empty string")),r&&(u.spaceBefore=!0),s&&(u.comment=s,u.range[2]=l),u}function wg({options:e},{offset:t,source:n,end:i},r){const s=new cl(n.substring(1));s.source===""&&r(t,"BAD_ALIAS","Alias cannot be an empty string"),s.source.endsWith(":")&&r(t+n.length-1,"BAD_ALIAS","Alias ending in : is ambiguous",!0);const o=t+n.length,a=qi(i,o,e.strict,r);return s.range=[t,o,a.offset],a.comment&&(s.comment=a.comment),s}function kg(e,t,{offset:n,start:i,value:r,end:s},o){const a=Object.assign({_directives:t},e),l=new Os(void 0,a),c={atKey:!1,atRoot:!0,directives:l.directives,options:l.options,schema:l.schema},h=jn(i,{indicator:"doc-start",next:r??(s==null?void 0:s[0]),offset:n,onError:o,parentIndent:0,startOnNewline:!0});h.found&&(l.directives.docStart=!0,r&&(r.type==="block-map"||r.type==="block-seq")&&!h.hasNewline&&o(h.end,"MISSING_CHAR","Block collection cannot start on same line with directives-end marker")),l.contents=r?$d(c,r,h,o):Sl(c,h.end,i,null,h,o);const u=l.contents.range[2],p=qi(s,u,!1,o);return p.comment&&(l.comment=p.comment),l.range=[n,u,p.offset],l}function ti(e){if(typeof e=="number")return[e,e+1];if(Array.isArray(e))return e.length===2?e:[e[0],e[1]];const{offset:t,source:n}=e;return[t,t+(typeof n=="string"?n.length:1)]}function zc(e){var r;let t="",n=!1,i=!1;for(let s=0;s<e.length;++s){const o=e[s];switch(o[0]){case"#":t+=(t===""?"":i?`

`:`
`)+(o.substring(1)||" "),n=!0,i=!1;break;case"%":((r=e[s+1])==null?void 0:r[0])!=="#"&&(s+=1),n=!1;break;default:n||(i=!0),n=!1}}return{comment:t,afterEmptyLine:i}}class Sg{constructor(t={}){this.doc=null,this.atDirectives=!1,this.prelude=[],this.errors=[],this.warnings=[],this.onError=(n,i,r,s)=>{const o=ti(n);s?this.warnings.push(new eg(o,i,r)):this.errors.push(new ai(o,i,r))},this.directives=new me({version:t.version||"1.2"}),this.options=t}decorate(t,n){const{comment:i,afterEmptyLine:r}=zc(this.prelude);if(i){const s=t.contents;if(n)t.comment=t.comment?`${t.comment}
${i}`:i;else if(r||t.directives.docStart||!s)t.commentBefore=i;else if(Y(s)&&!s.flow&&s.items.length>0){let o=s.items[0];X(o)&&(o=o.key);const a=o.commentBefore;o.commentBefore=a?`${i}
${a}`:i}else{const o=s.commentBefore;s.commentBefore=o?`${i}
${o}`:i}}if(n){for(let s=0;s<this.errors.length;++s)t.errors.push(this.errors[s]);for(let s=0;s<this.warnings.length;++s)t.warnings.push(this.warnings[s])}else t.errors=this.errors,t.warnings=this.warnings;this.prelude=[],this.errors=[],this.warnings=[]}streamInfo(){return{comment:zc(this.prelude).comment,directives:this.directives,errors:this.errors,warnings:this.warnings}}*compose(t,n=!1,i=-1){for(const r of t)yield*this.next(r);yield*this.end(n,i)}*next(t){switch(t.type){case"directive":this.directives.add(t.source,(n,i,r)=>{const s=ti(t);s[0]+=n,this.onError(s,"BAD_DIRECTIVE",i,r)}),this.prelude.push(t.source),this.atDirectives=!0;break;case"document":{const n=kg(this.options,this.directives,t,this.onError);this.atDirectives&&!n.directives.docStart&&this.onError(t,"MISSING_CHAR","Missing directives-end/doc-start indicator line"),this.decorate(n,!1),this.doc&&(yield this.doc),this.doc=n,this.atDirectives=!1;break}case"byte-order-mark":case"space":break;case"comment":case"newline":this.prelude.push(t.source);break;case"error":{const n=t.source?`${t.message}: ${JSON.stringify(t.source)}`:t.message,i=new ai(ti(t),"UNEXPECTED_TOKEN",n);this.atDirectives||!this.doc?this.errors.push(i):this.doc.errors.push(i);break}case"doc-end":{if(!this.doc){const i="Unexpected doc-end without preceding document";this.errors.push(new ai(ti(t),"UNEXPECTED_TOKEN",i));break}this.doc.directives.docEnd=!0;const n=qi(t.end,t.offset+t.source.length,this.doc.options.strict,this.onError);if(this.decorate(this.doc,!0),n.comment){const i=this.doc.comment;this.doc.comment=i?`${i}
${n.comment}`:n.comment}this.doc.range[2]=n.offset;break}default:this.errors.push(new ai(ti(t),"UNEXPECTED_TOKEN",`Unsupported token ${t.type}`))}}*end(t=!1,n=-1){if(this.doc)this.decorate(this.doc,!0),yield this.doc,this.doc=null;else if(t){const i=Object.assign({_directives:this.directives},this.options),r=new Os(void 0,i);this.atDirectives&&this.onError(n,"MISSING_CHAR","Missing directives-end indicator line"),r.range=[0,n,n],this.decorate(r,!1),yield r}}}const Fd="\uFEFF",zd="",Bd="",da="";function _g(e){switch(e){case Fd:return"byte-order-mark";case zd:return"doc-mode";case Bd:return"flow-error-end";case da:return"scalar";case"---":return"doc-start";case"...":return"doc-end";case"":case`
`:case`\r
`:return"newline";case"-":return"seq-item-ind";case"?":return"explicit-key-ind";case":":return"map-value-ind";case"{":return"flow-map-start";case"}":return"flow-map-end";case"[":return"flow-seq-start";case"]":return"flow-seq-end";case",":return"comma"}switch(e[0]){case" ":case"	":return"space";case"#":return"comment";case"%":return"directive-line";case"*":return"alias";case"&":return"anchor";case"!":return"tag";case"'":return"single-quoted-scalar";case'"':return"double-quoted-scalar";case"|":case">":return"block-scalar-header"}return null}function Be(e){switch(e){case void 0:case" ":case`
`:case"\r":case"	":return!0;default:return!1}}const Bc=new Set("0123456789ABCDEFabcdef"),bg=new Set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-#;/?:@&=+$_.!~*'()"),gr=new Set(",[]{}"),Eg=new Set(` ,[]{}
\r	`),po=e=>!e||Eg.has(e);class Cg{constructor(){this.atEnd=!1,this.blockScalarIndent=-1,this.blockScalarKeep=!1,this.buffer="",this.flowKey=!1,this.flowLevel=0,this.indentNext=0,this.indentValue=0,this.lineEndPos=null,this.next=null,this.pos=0}*lex(t,n=!1){if(t){if(typeof t!="string")throw TypeError("source is not a string");this.buffer=this.buffer?this.buffer+t:t,this.lineEndPos=null}this.atEnd=!n;let i=this.next??"stream";for(;i&&(n||this.hasChars(1));)i=yield*this.parseNext(i)}atLineEnd(){let t=this.pos,n=this.buffer[t];for(;n===" "||n==="	";)n=this.buffer[++t];return!n||n==="#"||n===`
`?!0:n==="\r"?this.buffer[t+1]===`
`:!1}charAt(t){return this.buffer[this.pos+t]}continueScalar(t){let n=this.buffer[t];if(this.indentNext>0){let i=0;for(;n===" ";)n=this.buffer[++i+t];if(n==="\r"){const r=this.buffer[i+t+1];if(r===`
`||!r&&!this.atEnd)return t+i+1}return n===`
`||i>=this.indentNext||!n&&!this.atEnd?t+i:-1}if(n==="-"||n==="."){const i=this.buffer.substr(t,3);if((i==="---"||i==="...")&&Be(this.buffer[t+3]))return-1}return t}getLine(){let t=this.lineEndPos;return(typeof t!="number"||t!==-1&&t<this.pos)&&(t=this.buffer.indexOf(`
`,this.pos),this.lineEndPos=t),t===-1?this.atEnd?this.buffer.substring(this.pos):null:(this.buffer[t-1]==="\r"&&(t-=1),this.buffer.substring(this.pos,t))}hasChars(t){return this.pos+t<=this.buffer.length}setNext(t){return this.buffer=this.buffer.substring(this.pos),this.pos=0,this.lineEndPos=null,this.next=t,null}peek(t){return this.buffer.substr(this.pos,t)}*parseNext(t){switch(t){case"stream":return yield*this.parseStream();case"line-start":return yield*this.parseLineStart();case"block-start":return yield*this.parseBlockStart();case"doc":return yield*this.parseDocument();case"flow":return yield*this.parseFlowCollection();case"quoted-scalar":return yield*this.parseQuotedScalar();case"block-scalar":return yield*this.parseBlockScalar();case"plain-scalar":return yield*this.parsePlainScalar()}}*parseStream(){let t=this.getLine();if(t===null)return this.setNext("stream");if(t[0]===Fd&&(yield*this.pushCount(1),t=t.substring(1)),t[0]==="%"){let n=t.length,i=t.indexOf("#");for(;i!==-1;){const s=t[i-1];if(s===" "||s==="	"){n=i-1;break}else i=t.indexOf("#",i+1)}for(;;){const s=t[n-1];if(s===" "||s==="	")n-=1;else break}const r=(yield*this.pushCount(n))+(yield*this.pushSpaces(!0));return yield*this.pushCount(t.length-r),this.pushNewline(),"stream"}if(this.atLineEnd()){const n=yield*this.pushSpaces(!0);return yield*this.pushCount(t.length-n),yield*this.pushNewline(),"stream"}return yield zd,yield*this.parseLineStart()}*parseLineStart(){const t=this.charAt(0);if(!t&&!this.atEnd)return this.setNext("line-start");if(t==="-"||t==="."){if(!this.atEnd&&!this.hasChars(4))return this.setNext("line-start");const n=this.peek(3);if((n==="---"||n==="...")&&Be(this.charAt(3)))return yield*this.pushCount(3),this.indentValue=0,this.indentNext=0,n==="---"?"doc":"stream"}return this.indentValue=yield*this.pushSpaces(!1),this.indentNext>this.indentValue&&!Be(this.charAt(1))&&(this.indentNext=this.indentValue),yield*this.parseBlockStart()}*parseBlockStart(){const[t,n]=this.peek(2);if(!n&&!this.atEnd)return this.setNext("block-start");if((t==="-"||t==="?"||t===":")&&Be(n)){const i=(yield*this.pushCount(1))+(yield*this.pushSpaces(!0));return this.indentNext=this.indentValue+1,this.indentValue+=i,"block-start"}return"doc"}*parseDocument(){yield*this.pushSpaces(!0);const t=this.getLine();if(t===null)return this.setNext("doc");let n=yield*this.pushIndicators();switch(t[n]){case"#":yield*this.pushCount(t.length-n);case void 0:return yield*this.pushNewline(),yield*this.parseLineStart();case"{":case"[":return yield*this.pushCount(1),this.flowKey=!1,this.flowLevel=1,"flow";case"}":case"]":return yield*this.pushCount(1),"doc";case"*":return yield*this.pushUntil(po),"doc";case'"':case"'":return yield*this.parseQuotedScalar();case"|":case">":return n+=yield*this.parseBlockScalarHeader(),n+=yield*this.pushSpaces(!0),yield*this.pushCount(t.length-n),yield*this.pushNewline(),yield*this.parseBlockScalar();default:return yield*this.parsePlainScalar()}}*parseFlowCollection(){let t,n,i=-1;do t=yield*this.pushNewline(),t>0?(n=yield*this.pushSpaces(!1),this.indentValue=i=n):n=0,n+=yield*this.pushSpaces(!0);while(t+n>0);const r=this.getLine();if(r===null)return this.setNext("flow");if((i!==-1&&i<this.indentNext&&r[0]!=="#"||i===0&&(r.startsWith("---")||r.startsWith("..."))&&Be(r[3]))&&!(i===this.indentNext-1&&this.flowLevel===1&&(r[0]==="]"||r[0]==="}")))return this.flowLevel=0,yield Bd,yield*this.parseLineStart();let s=0;for(;r[s]===",";)s+=yield*this.pushCount(1),s+=yield*this.pushSpaces(!0),this.flowKey=!1;switch(s+=yield*this.pushIndicators(),r[s]){case void 0:return"flow";case"#":return yield*this.pushCount(r.length-s),"flow";case"{":case"[":return yield*this.pushCount(1),this.flowKey=!1,this.flowLevel+=1,"flow";case"}":case"]":return yield*this.pushCount(1),this.flowKey=!0,this.flowLevel-=1,this.flowLevel?"flow":"doc";case"*":return yield*this.pushUntil(po),"flow";case'"':case"'":return this.flowKey=!0,yield*this.parseQuotedScalar();case":":{const o=this.charAt(1);if(this.flowKey||Be(o)||o===",")return this.flowKey=!1,yield*this.pushCount(1),yield*this.pushSpaces(!0),"flow"}default:return this.flowKey=!1,yield*this.parsePlainScalar()}}*parseQuotedScalar(){const t=this.charAt(0);let n=this.buffer.indexOf(t,this.pos+1);if(t==="'")for(;n!==-1&&this.buffer[n+1]==="'";)n=this.buffer.indexOf("'",n+2);else for(;n!==-1;){let s=0;for(;this.buffer[n-1-s]==="\\";)s+=1;if(s%2===0)break;n=this.buffer.indexOf('"',n+1)}const i=this.buffer.substring(0,n);let r=i.indexOf(`
`,this.pos);if(r!==-1){for(;r!==-1;){const s=this.continueScalar(r+1);if(s===-1)break;r=i.indexOf(`
`,s)}r!==-1&&(n=r-(i[r-1]==="\r"?2:1))}if(n===-1){if(!this.atEnd)return this.setNext("quoted-scalar");n=this.buffer.length}return yield*this.pushToIndex(n+1,!1),this.flowLevel?"flow":"doc"}*parseBlockScalarHeader(){this.blockScalarIndent=-1,this.blockScalarKeep=!1;let t=this.pos;for(;;){const n=this.buffer[++t];if(n==="+")this.blockScalarKeep=!0;else if(n>"0"&&n<="9")this.blockScalarIndent=Number(n)-1;else if(n!=="-")break}return yield*this.pushUntil(n=>Be(n)||n==="#")}*parseBlockScalar(){let t=this.pos-1,n=0,i;e:for(let s=this.pos;i=this.buffer[s];++s)switch(i){case" ":n+=1;break;case`
`:t=s,n=0;break;case"\r":{const o=this.buffer[s+1];if(!o&&!this.atEnd)return this.setNext("block-scalar");if(o===`
`)break}default:break e}if(!i&&!this.atEnd)return this.setNext("block-scalar");if(n>=this.indentNext){this.blockScalarIndent===-1?this.indentNext=n:this.indentNext=this.blockScalarIndent+(this.indentNext===0?1:this.indentNext);do{const s=this.continueScalar(t+1);if(s===-1)break;t=this.buffer.indexOf(`
`,s)}while(t!==-1);if(t===-1){if(!this.atEnd)return this.setNext("block-scalar");t=this.buffer.length}}let r=t+1;for(i=this.buffer[r];i===" ";)i=this.buffer[++r];if(i==="	"){for(;i==="	"||i===" "||i==="\r"||i===`
`;)i=this.buffer[++r];t=r-1}else if(!this.blockScalarKeep)do{let s=t-1,o=this.buffer[s];o==="\r"&&(o=this.buffer[--s]);const a=s;for(;o===" ";)o=this.buffer[--s];if(o===`
`&&s>=this.pos&&s+1+n>a)t=s;else break}while(!0);return yield da,yield*this.pushToIndex(t+1,!0),yield*this.parseLineStart()}*parsePlainScalar(){const t=this.flowLevel>0;let n=this.pos-1,i=this.pos-1,r;for(;r=this.buffer[++i];)if(r===":"){const s=this.buffer[i+1];if(Be(s)||t&&gr.has(s))break;n=i}else if(Be(r)){let s=this.buffer[i+1];if(r==="\r"&&(s===`
`?(i+=1,r=`
`,s=this.buffer[i+1]):n=i),s==="#"||t&&gr.has(s))break;if(r===`
`){const o=this.continueScalar(i+1);if(o===-1)break;i=Math.max(i,o-2)}}else{if(t&&gr.has(r))break;n=i}return!r&&!this.atEnd?this.setNext("plain-scalar"):(yield da,yield*this.pushToIndex(n+1,!0),t?"flow":"doc")}*pushCount(t){return t>0?(yield this.buffer.substr(this.pos,t),this.pos+=t,t):0}*pushToIndex(t,n){const i=this.buffer.slice(this.pos,t);return i?(yield i,this.pos+=i.length,i.length):(n&&(yield""),0)}*pushIndicators(){let t=0;e:for(;;){switch(this.charAt(0)){case"!":t+=yield*this.pushTag(),t+=yield*this.pushSpaces(!0);continue e;case"&":t+=yield*this.pushUntil(po),t+=yield*this.pushSpaces(!0);continue e;case"-":case"?":case":":{const n=this.flowLevel>0,i=this.charAt(1);if(Be(i)||n&&gr.has(i)){n?this.flowKey&&(this.flowKey=!1):this.indentNext=this.indentValue+1,t+=yield*this.pushCount(1),t+=yield*this.pushSpaces(!0);continue e}}}break e}return t}*pushTag(){if(this.charAt(1)==="<"){let t=this.pos+2,n=this.buffer[t];for(;!Be(n)&&n!==">";)n=this.buffer[++t];return yield*this.pushToIndex(n===">"?t+1:t,!1)}else{let t=this.pos+1,n=this.buffer[t];for(;n;)if(bg.has(n))n=this.buffer[++t];else if(n==="%"&&Bc.has(this.buffer[t+1])&&Bc.has(this.buffer[t+2]))n=this.buffer[t+=3];else break;return yield*this.pushToIndex(t,!1)}}*pushNewline(){const t=this.buffer[this.pos];return t===`
`?yield*this.pushCount(1):t==="\r"&&this.charAt(1)===`
`?yield*this.pushCount(2):0}*pushSpaces(t){let n=this.pos-1,i;do i=this.buffer[++n];while(i===" "||t&&i==="	");const r=n-this.pos;return r>0&&(yield this.buffer.substr(this.pos,r),this.pos=n),r}*pushUntil(t){let n=this.pos,i=this.buffer[n];for(;!t(i);)i=this.buffer[++n];return yield*this.pushToIndex(n,!1)}}class Mg{constructor(){this.lineStarts=[],this.addNewLine=t=>this.lineStarts.push(t),this.linePos=t=>{let n=0,i=this.lineStarts.length;for(;n<i;){const s=n+i>>1;this.lineStarts[s]<t?n=s+1:i=s}if(this.lineStarts[n]===t)return{line:n+1,col:1};if(n===0)return{line:0,col:t};const r=this.lineStarts[n-1];return{line:n,col:t-r+1}}}}function gt(e,t){for(let n=0;n<e.length;++n)if(e[n].type===t)return!0;return!1}function Hc(e){for(let t=0;t<e.length;++t)switch(e[t].type){case"space":case"comment":case"newline":break;default:return t}return-1}function Hd(e){switch(e==null?void 0:e.type){case"alias":case"scalar":case"single-quoted-scalar":case"double-quoted-scalar":case"flow-collection":return!0;default:return!1}}function yr(e){switch(e.type){case"document":return e.start;case"block-map":{const t=e.items[e.items.length-1];return t.sep??t.start}case"block-seq":return e.items[e.items.length-1].start;default:return[]}}function sn(e){var n;if(e.length===0)return[];let t=e.length;e:for(;--t>=0;)switch(e[t].type){case"doc-start":case"explicit-key-ind":case"map-value-ind":case"seq-item-ind":case"newline":break e}for(;((n=e[++t])==null?void 0:n.type)==="space";);return e.splice(t,e.length)}function ss(e,t){if(t.length<1e5)Array.prototype.push.apply(e,t);else for(let n=0;n<t.length;++n)e.push(t[n])}function Vc(e){if(e.start.type==="flow-seq-start")for(const t of e.items)t.sep&&!t.value&&!gt(t.start,"explicit-key-ind")&&!gt(t.sep,"map-value-ind")&&(t.key&&(t.value=t.key),delete t.key,Hd(t.value)?t.value.end?ss(t.value.end,t.sep):t.value.end=t.sep:ss(t.start,t.sep),delete t.sep)}class Ag{constructor(t){this.atNewLine=!0,this.atScalar=!1,this.indent=0,this.offset=0,this.onKeyLine=!1,this.stack=[],this.source="",this.type="",this.lexer=new Cg,this.onNewLine=t}*parse(t,n=!1){this.onNewLine&&this.offset===0&&this.onNewLine(0);for(const i of this.lexer.lex(t,n))yield*this.next(i);n||(yield*this.end())}*next(t){if(this.source=t,this.atScalar){this.atScalar=!1,yield*this.step(),this.offset+=t.length;return}const n=_g(t);if(n)if(n==="scalar")this.atNewLine=!1,this.atScalar=!0,this.type="scalar";else{switch(this.type=n,yield*this.step(),n){case"newline":this.atNewLine=!0,this.indent=0,this.onNewLine&&this.onNewLine(this.offset+t.length);break;case"space":this.atNewLine&&t[0]===" "&&(this.indent+=t.length);break;case"explicit-key-ind":case"map-value-ind":case"seq-item-ind":this.atNewLine&&(this.indent+=t.length);break;case"doc-mode":case"flow-error-end":return;default:this.atNewLine=!1}this.offset+=t.length}else{const i=`Not a YAML token: ${t}`;yield*this.pop({type:"error",offset:this.offset,message:i,source:t}),this.offset+=t.length}}*end(){for(;this.stack.length>0;)yield*this.pop()}get sourceToken(){return{type:this.type,offset:this.offset,indent:this.indent,source:this.source}}*step(){const t=this.peek(1);if(this.type==="doc-end"&&(t==null?void 0:t.type)!=="doc-end"){for(;this.stack.length>0;)yield*this.pop();this.stack.push({type:"doc-end",offset:this.offset,source:this.source});return}if(!t)return yield*this.stream();switch(t.type){case"document":return yield*this.document(t);case"alias":case"scalar":case"single-quoted-scalar":case"double-quoted-scalar":return yield*this.scalar(t);case"block-scalar":return yield*this.blockScalar(t);case"block-map":return yield*this.blockMap(t);case"block-seq":return yield*this.blockSequence(t);case"flow-collection":return yield*this.flowCollection(t);case"doc-end":return yield*this.documentEnd(t)}yield*this.pop()}peek(t){return this.stack[this.stack.length-t]}*pop(t){const n=t??this.stack.pop();if(!n)yield{type:"error",offset:this.offset,source:"",message:"Tried to pop an empty stack"};else if(this.stack.length===0)yield n;else{const i=this.peek(1);switch(n.type==="block-scalar"?n.indent="indent"in i?i.indent:0:n.type==="flow-collection"&&i.type==="document"&&(n.indent=0),n.type==="flow-collection"&&Vc(n),i.type){case"document":i.value=n;break;case"block-scalar":i.props.push(n);break;case"block-map":{const r=i.items[i.items.length-1];if(r.value){i.items.push({start:[],key:n,sep:[]}),this.onKeyLine=!0;return}else if(r.sep)r.value=n;else{Object.assign(r,{key:n,sep:[]}),this.onKeyLine=!r.explicitKey;return}break}case"block-seq":{const r=i.items[i.items.length-1];r.value?i.items.push({start:[],value:n}):r.value=n;break}case"flow-collection":{const r=i.items[i.items.length-1];!r||r.value?i.items.push({start:[],key:n,sep:[]}):r.sep?r.value=n:Object.assign(r,{key:n,sep:[]});return}default:yield*this.pop(),yield*this.pop(n)}if((i.type==="document"||i.type==="block-map"||i.type==="block-seq")&&(n.type==="block-map"||n.type==="block-seq")){const r=n.items[n.items.length-1];r&&!r.sep&&!r.value&&r.start.length>0&&Hc(r.start)===-1&&(n.indent===0||r.start.every(s=>s.type!=="comment"||s.indent<n.indent))&&(i.type==="document"?i.end=r.start:i.items.push({start:r.start}),n.items.splice(-1,1))}}}*stream(){switch(this.type){case"directive-line":yield{type:"directive",offset:this.offset,source:this.source};return;case"byte-order-mark":case"space":case"comment":case"newline":yield this.sourceToken;return;case"doc-mode":case"doc-start":{const t={type:"document",offset:this.offset,start:[]};this.type==="doc-start"&&t.start.push(this.sourceToken),this.stack.push(t);return}}yield{type:"error",offset:this.offset,message:`Unexpected ${this.type} token in YAML stream`,source:this.source}}*document(t){if(t.value)return yield*this.lineEnd(t);switch(this.type){case"doc-start":{Hc(t.start)!==-1?(yield*this.pop(),yield*this.step()):t.start.push(this.sourceToken);return}case"anchor":case"tag":case"space":case"comment":case"newline":t.start.push(this.sourceToken);return}const n=this.startBlockValue(t);n?this.stack.push(n):yield{type:"error",offset:this.offset,message:`Unexpected ${this.type} token in YAML document`,source:this.source}}*scalar(t){if(this.type==="map-value-ind"){const n=yr(this.peek(2)),i=sn(n);let r;t.end?(r=t.end,r.push(this.sourceToken),delete t.end):r=[this.sourceToken];const s={type:"block-map",offset:t.offset,indent:t.indent,items:[{start:i,key:t,sep:r}]};this.onKeyLine=!0,this.stack[this.stack.length-1]=s}else yield*this.lineEnd(t)}*blockScalar(t){switch(this.type){case"space":case"comment":case"newline":t.props.push(this.sourceToken);return;case"scalar":if(t.source=this.source,this.atNewLine=!0,this.indent=0,this.onNewLine){let n=this.source.indexOf(`
`)+1;for(;n!==0;)this.onNewLine(this.offset+n),n=this.source.indexOf(`
`,n)+1}yield*this.pop();break;default:yield*this.pop(),yield*this.step()}}*blockMap(t){var i;const n=t.items[t.items.length-1];switch(this.type){case"newline":if(this.onKeyLine=!1,n.value){const r="end"in n.value?n.value.end:void 0,s=Array.isArray(r)?r[r.length-1]:void 0;(s==null?void 0:s.type)==="comment"?r==null||r.push(this.sourceToken):t.items.push({start:[this.sourceToken]})}else n.sep?n.sep.push(this.sourceToken):n.start.push(this.sourceToken);return;case"space":case"comment":if(n.value)t.items.push({start:[this.sourceToken]});else if(n.sep)n.sep.push(this.sourceToken);else{if(this.atIndentedComment(n.start,t.indent)){const r=t.items[t.items.length-2],s=(i=r==null?void 0:r.value)==null?void 0:i.end;if(Array.isArray(s)){ss(s,n.start),s.push(this.sourceToken),t.items.pop();return}}n.start.push(this.sourceToken)}return}if(this.indent>=t.indent){const r=!this.onKeyLine&&this.indent===t.indent,s=r&&(n.sep||n.explicitKey)&&this.type!=="seq-item-ind";let o=[];if(s&&n.sep&&!n.value){const a=[];for(let l=0;l<n.sep.length;++l){const c=n.sep[l];switch(c.type){case"newline":a.push(l);break;case"space":break;case"comment":c.indent>t.indent&&(a.length=0);break;default:a.length=0}}a.length>=2&&(o=n.sep.splice(a[1]))}switch(this.type){case"anchor":case"tag":s||n.value?(o.push(this.sourceToken),t.items.push({start:o}),this.onKeyLine=!0):n.sep?n.sep.push(this.sourceToken):n.start.push(this.sourceToken);return;case"explicit-key-ind":!n.sep&&!n.explicitKey?(n.start.push(this.sourceToken),n.explicitKey=!0):s||n.value?(o.push(this.sourceToken),t.items.push({start:o,explicitKey:!0})):this.stack.push({type:"block-map",offset:this.offset,indent:this.indent,items:[{start:[this.sourceToken],explicitKey:!0}]}),this.onKeyLine=!0;return;case"map-value-ind":if(n.explicitKey)if(n.sep)if(n.value)t.items.push({start:[],key:null,sep:[this.sourceToken]});else if(gt(n.sep,"map-value-ind"))this.stack.push({type:"block-map",offset:this.offset,indent:this.indent,items:[{start:o,key:null,sep:[this.sourceToken]}]});else if(Hd(n.key)&&!gt(n.sep,"newline")){const a=sn(n.start),l=n.key,c=n.sep;c.push(this.sourceToken),delete n.key,delete n.sep,this.stack.push({type:"block-map",offset:this.offset,indent:this.indent,items:[{start:a,key:l,sep:c}]})}else o.length>0?n.sep=n.sep.concat(o,this.sourceToken):n.sep.push(this.sourceToken);else if(gt(n.start,"newline"))Object.assign(n,{key:null,sep:[this.sourceToken]});else{const a=sn(n.start);this.stack.push({type:"block-map",offset:this.offset,indent:this.indent,items:[{start:a,key:null,sep:[this.sourceToken]}]})}else n.sep?n.value||s?t.items.push({start:o,key:null,sep:[this.sourceToken]}):gt(n.sep,"map-value-ind")?this.stack.push({type:"block-map",offset:this.offset,indent:this.indent,items:[{start:[],key:null,sep:[this.sourceToken]}]}):n.sep.push(this.sourceToken):Object.assign(n,{key:null,sep:[this.sourceToken]});this.onKeyLine=!0;return;case"alias":case"scalar":case"single-quoted-scalar":case"double-quoted-scalar":{const a=this.flowScalar(this.type);s||n.value?(t.items.push({start:o,key:a,sep:[]}),this.onKeyLine=!0):n.sep?this.stack.push(a):(Object.assign(n,{key:a,sep:[]}),this.onKeyLine=!0);return}default:{const a=this.startBlockValue(t);if(a){if(a.type==="block-seq"){if(!n.explicitKey&&n.sep&&!gt(n.sep,"newline")){yield*this.pop({type:"error",offset:this.offset,message:"Unexpected block-seq-ind on same line with key",source:this.source});return}}else r&&t.items.push({start:o});this.stack.push(a);return}}}}yield*this.pop(),yield*this.step()}*blockSequence(t){var i;const n=t.items[t.items.length-1];switch(this.type){case"newline":if(n.value){const r="end"in n.value?n.value.end:void 0,s=Array.isArray(r)?r[r.length-1]:void 0;(s==null?void 0:s.type)==="comment"?r==null||r.push(this.sourceToken):t.items.push({start:[this.sourceToken]})}else n.start.push(this.sourceToken);return;case"space":case"comment":if(n.value)t.items.push({start:[this.sourceToken]});else{if(this.atIndentedComment(n.start,t.indent)){const r=t.items[t.items.length-2],s=(i=r==null?void 0:r.value)==null?void 0:i.end;if(Array.isArray(s)){ss(s,n.start),s.push(this.sourceToken),t.items.pop();return}}n.start.push(this.sourceToken)}return;case"anchor":case"tag":if(n.value||this.indent<=t.indent)break;n.start.push(this.sourceToken);return;case"seq-item-ind":if(this.indent!==t.indent)break;n.value||gt(n.start,"seq-item-ind")?t.items.push({start:[this.sourceToken]}):n.start.push(this.sourceToken);return}if(this.indent>t.indent){const r=this.startBlockValue(t);if(r){this.stack.push(r);return}}yield*this.pop(),yield*this.step()}*flowCollection(t){const n=t.items[t.items.length-1];if(this.type==="flow-error-end"){let i;do yield*this.pop(),i=this.peek(1);while((i==null?void 0:i.type)==="flow-collection")}else if(t.end.length===0){switch(this.type){case"comma":case"explicit-key-ind":!n||n.sep?t.items.push({start:[this.sourceToken]}):n.start.push(this.sourceToken);return;case"map-value-ind":!n||n.value?t.items.push({start:[],key:null,sep:[this.sourceToken]}):n.sep?n.sep.push(this.sourceToken):Object.assign(n,{key:null,sep:[this.sourceToken]});return;case"space":case"comment":case"newline":case"anchor":case"tag":!n||n.value?t.items.push({start:[this.sourceToken]}):n.sep?n.sep.push(this.sourceToken):n.start.push(this.sourceToken);return;case"alias":case"scalar":case"single-quoted-scalar":case"double-quoted-scalar":{const r=this.flowScalar(this.type);!n||n.value?t.items.push({start:[],key:r,sep:[]}):n.sep?this.stack.push(r):Object.assign(n,{key:r,sep:[]});return}case"flow-map-end":case"flow-seq-end":t.end.push(this.sourceToken);return}const i=this.startBlockValue(t);i?this.stack.push(i):(yield*this.pop(),yield*this.step())}else{const i=this.peek(2);if(i.type==="block-map"&&(this.type==="map-value-ind"&&i.indent===t.indent||this.type==="newline"&&!i.items[i.items.length-1].sep))yield*this.pop(),yield*this.step();else if(this.type==="map-value-ind"&&i.type!=="flow-collection"){const r=yr(i),s=sn(r);Vc(t);const o=t.end.splice(1,t.end.length);o.push(this.sourceToken);const a={type:"block-map",offset:t.offset,indent:t.indent,items:[{start:s,key:t,sep:o}]};this.onKeyLine=!0,this.stack[this.stack.length-1]=a}else yield*this.lineEnd(t)}}flowScalar(t){if(this.onNewLine){let n=this.source.indexOf(`
`)+1;for(;n!==0;)this.onNewLine(this.offset+n),n=this.source.indexOf(`
`,n)+1}return{type:t,offset:this.offset,indent:this.indent,source:this.source}}startBlockValue(t){switch(this.type){case"alias":case"scalar":case"single-quoted-scalar":case"double-quoted-scalar":return this.flowScalar(this.type);case"block-scalar-header":return{type:"block-scalar",offset:this.offset,indent:this.indent,props:[this.sourceToken],source:""};case"flow-map-start":case"flow-seq-start":return{type:"flow-collection",offset:this.offset,indent:this.indent,start:this.sourceToken,items:[],end:[]};case"seq-item-ind":return{type:"block-seq",offset:this.offset,indent:this.indent,items:[{start:[this.sourceToken]}]};case"explicit-key-ind":{this.onKeyLine=!0;const n=yr(t),i=sn(n);return i.push(this.sourceToken),{type:"block-map",offset:this.offset,indent:this.indent,items:[{start:i,explicitKey:!0}]}}case"map-value-ind":{this.onKeyLine=!0;const n=yr(t),i=sn(n);return{type:"block-map",offset:this.offset,indent:this.indent,items:[{start:i,key:null,sep:[this.sourceToken]}]}}}return null}atIndentedComment(t,n){return this.type!=="comment"||this.indent<=n?!1:t.every(i=>i.type==="newline"||i.type==="space")}*documentEnd(t){this.type!=="doc-mode"&&(t.end?t.end.push(this.sourceToken):t.end=[this.sourceToken],this.type==="newline"&&(yield*this.pop()))}*lineEnd(t){switch(this.type){case"comma":case"doc-start":case"doc-end":case"flow-seq-end":case"flow-map-end":case"map-value-ind":yield*this.pop(),yield*this.step();break;case"newline":this.onKeyLine=!1;case"space":case"comment":default:t.end?t.end.push(this.sourceToken):t.end=[this.sourceToken],this.type==="newline"&&(yield*this.pop())}}}function Ng(e){const t=e.prettyErrors!==!1;return{lineCounter:e.lineCounter||t&&new Mg||null,prettyErrors:t}}function Tg(e,t={}){const{lineCounter:n,prettyErrors:i}=Ng(t),r=new Ag(n==null?void 0:n.addNewLine),s=new Sg(t);let o=null;for(const a of s.compose(r.parse(e),!0,e.length))if(!o)o=a;else if(o.options.logLevel!=="silent"){o.errors.push(new ai(a.range.slice(0,2),"MULTIPLE_DOCS","Source contains multiple documents; please use YAML.parseAllDocuments()"));break}return i&&n&&(o.errors.forEach($c(e,n)),o.warnings.forEach($c(e,n))),o}function _l(e,t,n){let i;const r=Tg(e,n);if(!r)return null;if(r.warnings.forEach(s=>hd(r.options.logLevel,s)),r.errors.length>0){if(r.options.logLevel!=="silent")throw r.errors[0];r.errors=[]}return r.toJS(Object.assign({reviver:i},n))}const Ig=`# Dashboard layout for the Actor role at a Theatre / Drama Academy (ADR-0004 profile theatre-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: actor
title: "Actor"
extends: student
widgets:
  - productions.my-roles
  - selection-process.upcoming
  - facility-booking.my-bookings
  - portfolio.my-portfolio
  - inventory-equipment.my-loans
`,Og=`# Dashboard layout for the Applicant role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: applicant
title: "Applicant"
widgets:
  - admissions.application-status
  - admissions.pending-documents
  - fees-accounts.fee-due
  - web-portal-cms.announcements
`,Lg=`# Dashboard layout for the Artist role at a Arts Academy / Fine Arts College (ADR-0004 profile arts-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: artist
title: "Artist"
extends: student
widgets:
  - portfolio.my-portfolio
  - projects.my-projects
  - facility-booking.my-bookings
  - selection-process.upcoming
  - productions.upcoming
  - inventory-equipment.my-loans
`,Dg=`# Dashboard layout for the Athlete role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: athlete
title: "Athlete"
extends: student
widgets:
  - athlete-performance.training-schedule
  - athlete-performance.performance-trend
  - sports-nutrition-health.nutrition-plan
  - tournament-events.upcoming
`,xg=`# Dashboard layout for the Chef / Operations Instructor role at a Hospitality / Hotel Management (ADR-0004 profile hospitality-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: chef-instructor
title: "Chef / Operations Instructor"
extends: faculty
widgets:
  - skill-progress.assessments-due
  - facility-booking.bookings-today
  - inventory-equipment.low-stock
  - productions.in-preparation
`,Rg=`# Dashboard layout for the Choreographer role at a Dance / Performing Arts Academy (ADR-0004 profile dance-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: choreographer
title: "Choreographer"
extends: faculty
widgets:
  - productions.in-preparation
  - selection-process.to-judge
  - skill-progress.assessments-due
  - facility-booking.bookings-today
`,Pg=`# Dashboard layout for the Clinical Supervisor role at a Medical / Health Sciences College (ADR-0004 profile medical-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: clinical-supervisor
title: "Clinical Supervisor"
extends: faculty
widgets:
  - field-training.trainees-to-assess
  - skill-progress.assessments-due
  - field-training.placements-open
  - facility-booking.bookings-today
`,jg=`# Dashboard layout for the Coach role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: coach
title: "Coach"
extends: faculty
widgets:
  - athlete-performance.squad-overview
  - athlete-performance.session-plan
  - training-video-analysis.reviews-pending
  - facility-booking.bookings
  - wearables.alerts
  - tournament-events.calendar
`,$g=`# Dashboard layout for the Corporate Mentor role at a Management / Business School (ADR-0004 profile management-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: corporate-mentor
title: "Corporate Mentor"
extends: faculty
widgets:
  - projects.to-review
  - field-training.trainees-to-assess
  - selection-process.to-judge
  - productions.in-preparation
`,Fg=`# Dashboard layout for the Dancer role at a Dance / Performing Arts Academy (ADR-0004 profile dance-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: dancer
title: "Dancer"
extends: student
widgets:
  - skill-progress.my-progress
  - productions.my-roles
  - selection-process.upcoming
  - facility-booking.my-bookings
  - inventory-equipment.my-loans
  - timetable-attendance.today
`,zg=`# Dashboard layout for the Department Admin / HoD role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: department-admin
title: "Department Admin / HoD"
widgets:
  - workflow.approvals-pending
  - academic-management.faculty-load
  - timetable-attendance.department-attendance
  - examinations.results-summary
  - reporting.department-reports
`,Bg=`# Dashboard layout for the Design Mentor role at a Design / Fashion Institute (ADR-0004 profile design-fashion-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: design-mentor
title: "Design Mentor"
extends: faculty
widgets:
  - portfolio.reviews-pending
  - projects.to-review
  - selection-process.to-judge
  - field-training.trainees-to-assess
`,Hg=`# Dashboard layout for the Designer role at a Design / Fashion Institute (ADR-0004 profile design-fashion-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: designer
title: "Designer"
extends: student
widgets:
  - portfolio.my-portfolio
  - projects.my-projects
  - productions.upcoming
  - facility-booking.my-bookings
  - field-training.my-placement
  - selection-process.upcoming
`,Vg=`# Dashboard layout for the Director role at a Theatre / Drama Academy (ADR-0004 profile theatre-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: director
title: "Director"
extends: faculty
widgets:
  - productions.in-preparation
  - selection-process.to-judge
  - projects.to-review
  - facility-booking.bookings-today
`,Ug=`# Dashboard layout for the Engineering Student role at a Engineering / Technology College (ADR-0004 profile engineering-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: engineering-student
title: "Engineering Student"
extends: student
widgets:
  - projects.my-projects
  - projects.milestones-due
  - facility-booking.my-bookings
  - field-training.my-placement
  - productions.upcoming
  - placement-career.openings
`,Kg=`# Dashboard layout for the Ensemble / Orchestra Director role at a Music Academy / Conservatory (ADR-0004 profile music-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: ensemble-director
title: "Ensemble / Orchestra Director"
widgets:
  - productions.in-preparation
  - productions.calendar
  - selection-process.open-calls
  - inventory-equipment.low-stock
`,Wg=`# Dashboard layout for the Equipment Manager role at a Film / Media / Animation Institute (ADR-0004 profile film-media-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: equipment-manager
title: "Equipment Manager"
widgets:
  - inventory-equipment.low-stock
  - inventory-equipment.overdue-loans
  - facility-booking.bookings-today
  - maintenance.tickets
`,qg=`# Dashboard layout for the Examination Staff role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: examination-staff
title: "Examination Staff"
widgets:
  - examinations.schedule
  - examinations.hall-tickets-issued
  - examinations.results-pending
  - enrolment-registration.registered-candidates
`,Qg=`# Dashboard layout for the Exhibition & Gallery Manager role at a Arts Academy / Fine Arts College (ADR-0004 profile arts-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: exhibition-manager
title: "Exhibition & Gallery Manager"
widgets:
  - productions.calendar
  - productions.upcoming
  - facility-booking.bookings-today
  - inventory-equipment.low-stock
`,Gg=`# Dashboard layout for the Facility / Inventory Staff role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: facility-staff
title: "Facility / Inventory Staff"
widgets:
  - facility-booking.bookings-today
  - maintenance.tickets
  - inventory-equipment.low-stock
  - asset-management.audit-due
`,Yg=`# Dashboard layout for the Faculty / Instructor role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: faculty
title: "Faculty / Instructor"
widgets:
  - timetable-attendance.today-classes
  - timetable-attendance.attendance-to-mark
  - lms.assignments-to-grade
  - examinations.exam-duties
  - academic-management.course-roster
`,Jg=`# Dashboard layout for the Farm Supervisor role at a Agriculture / Veterinary / Field Sciences (ADR-0004 profile agriculture-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: farm-supervisor
title: "Farm Supervisor"
extends: faculty
widgets:
  - field-training.trainees-to-assess
  - facility-booking.bookings-today
  - inventory-equipment.low-stock
  - projects.active
`,Xg=`# Dashboard layout for the Field Trainee role at a Agriculture / Veterinary / Field Sciences (ADR-0004 profile agriculture-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: field-trainee
title: "Field Trainee"
extends: student
widgets:
  - field-training.my-placement
  - field-training.hours-logged
  - projects.my-projects
  - facility-booking.my-bookings
  - skill-progress.my-progress
`,Zg=`# Dashboard layout for the Filmmaker role at a Film / Media / Animation Institute (ADR-0004 profile film-media-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: filmmaker
title: "Filmmaker"
extends: student
widgets:
  - projects.my-projects
  - projects.milestones-due
  - facility-booking.my-bookings
  - inventory-equipment.my-loans
  - portfolio.my-portfolio
  - productions.upcoming
`,ey=`# Dashboard layout for the Finance Staff role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: finance-staff
title: "Finance Staff"
widgets:
  - fees-accounts.collections-today
  - fees-accounts.outstanding-dues
  - payment-sbiepay.reconciliation
  - budget-grants.budget-vs-spend
  - procurement.purchase-orders-pending
`,ty=`# Dashboard layout for the Governance (Grievance / RTI / IQAC) role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: governance
title: "Governance (Grievance / RTI / IQAC)"
widgets:
  - grievance.open-by-committee
  - rti.nearing-deadline
  - iqac-accreditation.action-items
  - regulatory-reports.due
`,ny=`# Dashboard layout for the Hospital Coordinator role at a Medical / Health Sciences College (ADR-0004 profile medical-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: hospital-coordinator
title: "Hospital Coordinator"
widgets:
  - field-training.active-placements
  - field-training.placements-open
  - facility-booking.bookings-today
  - regulatory-reports.due
`,iy=`# Dashboard layout for the Hospitality Trainee role at a Hospitality / Hotel Management (ADR-0004 profile hospitality-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: hospitality-trainee
title: "Hospitality Trainee"
extends: student
widgets:
  - field-training.my-placement
  - skill-progress.my-progress
  - facility-booking.my-bookings
  - productions.upcoming
  - inventory-equipment.my-loans
  - placement-career.openings
`,ry=`# Dashboard layout for the HR Staff role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: hr-staff
title: "HR Staff"
widgets:
  - hr-payroll.leave-requests
  - hr-payroll.payroll-run-status
  - e-office.files-pending
  - hr-payroll.joinings-and-exits
`,sy=`# Dashboard layout for the Industry Coordinator role at a Hospitality / Hotel Management (ADR-0004 profile hospitality-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: industry-coordinator
title: "Industry Coordinator"
widgets:
  - field-training.placements-open
  - field-training.active-placements
  - placement-career.openings
  - productions.calendar
`,oy=`# Dashboard layout for the Industry Liaison role at a Design / Fashion Institute (ADR-0004 profile design-fashion-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: industry-liaison
title: "Industry Liaison"
widgets:
  - field-training.placements-open
  - projects.active
  - productions.calendar
  - placement-career.openings
`,ay=`# Dashboard layout for the Lab In-charge role at a Engineering / Technology College (ADR-0004 profile engineering-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: lab-in-charge
title: "Lab In-charge"
widgets:
  - facility-booking.bookings-today
  - inventory-equipment.low-stock
  - inventory-equipment.overdue-loans
  - maintenance.tickets
`,ly=`# Dashboard layout for the Law Student role at a Law College / Law University (ADR-0004 profile law-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: law-student
title: "Law Student"
extends: student
widgets:
  - selection-process.upcoming
  - productions.upcoming
  - field-training.my-placement
  - projects.my-projects
  - field-training.hours-logged
  - placement-career.openings
`,cy=`# Dashboard layout for the Legal Mentor role at a Law College / Law University (ADR-0004 profile law-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: legal-mentor
title: "Legal Mentor"
extends: faculty
widgets:
  - projects.to-review
  - selection-process.to-judge
  - field-training.trainees-to-assess
  - productions.in-preparation
`,uy=`# Dashboard layout for the Management Student role at a Management / Business School (ADR-0004 profile management-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: management-student
title: "Management Student"
extends: student
widgets:
  - productions.upcoming
  - projects.my-projects
  - field-training.my-placement
  - placement-career.openings
  - alumni.mentoring
  - lms.course-materials
`,fy=`# Dashboard layout for the Management (VC, Registrar) role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: management
title: "Management (VC, Registrar)"
widgets:
  - admissions.funnel
  - fees-accounts.collection-vs-target
  - reporting.attendance-and-results-by-department
  - grievance.open
  - regulatory-reports.compliance-calendar
  - productions.upcoming
`,dy=`# Dashboard layout for the Medical Staff (Doctor / Physio) role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: medical-staff
title: "Medical Staff (Doctor / Physio)"
widgets:
  - sports-nutrition-health.injured-athletes
  - sports-nutrition-health.appointments-today
  - athlete-performance.fitness-clearances
  - facility-booking.bookings
`,py=`# Dashboard layout for the Medical Student role at a Medical / Health Sciences College (ADR-0004 profile medical-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: medical-student
title: "Medical Student"
extends: student
widgets:
  - field-training.my-placement
  - field-training.hours-logged
  - skill-progress.my-progress
  - facility-booking.my-bookings
  - projects.my-projects
  - lms.course-materials
`,hy=`# Dashboard layout for the Mentor Teacher role at a Teacher Education / B.Ed. (ADR-0004 profile teacher-education-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: mentor-teacher
title: "Mentor Teacher"
extends: faculty
widgets:
  - field-training.trainees-to-assess
  - portfolio.reviews-pending
  - projects.to-review
  - skill-progress.assessments-due
`,my=`# Dashboard layout for the Moot Court Coordinator role at a Law College / Law University (ADR-0004 profile law-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: moot-court-coordinator
title: "Moot Court Coordinator"
widgets:
  - selection-process.open-calls
  - productions.calendar
  - productions.upcoming
  - field-training.placements-open
`,gy=`# Dashboard layout for the Music Teacher role at a Music Academy / Conservatory (ADR-0004 profile music-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: music-teacher
title: "Music Teacher"
extends: faculty
widgets:
  - skill-progress.assessments-due
  - selection-process.to-judge
  - portfolio.reviews-pending
  - facility-booking.bookings-today
`,yy=`# Dashboard layout for the Musician role at a Music Academy / Conservatory (ADR-0004 profile music-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: musician
title: "Musician"
extends: student
widgets:
  - portfolio.my-portfolio
  - facility-booking.my-bookings
  - selection-process.upcoming
  - productions.upcoming
  - skill-progress.my-progress
  - inventory-equipment.my-loans
`,vy=`# Dashboard layout for the Nutritionist role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: nutritionist
title: "Nutritionist"
widgets:
  - sports-nutrition-health.athletes-on-plans
  - sports-nutrition-health.plan-reviews-due
  - athlete-performance.body-composition-trend
`,wy=`# Dashboard layout for the Organisation Admin role (ADR-0005). Exists in every organisation.
role: org-admin
title: "Organisation Admin"
widgets:
  - billing.plan-and-trial
  - billing.usage-vs-limits
  - tenancy.enabled-modules
  - identity.users-and-roles
  - billing.invoices
  - audit.recent-activity
`,ky=`# Dashboard layout for the Placement Officer role at a Management / Business School (ADR-0004 profile management-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: placement-officer
title: "Placement Officer"
widgets:
  - field-training.placements-open
  - placement-career.openings
  - placement-career.drives
  - productions.calendar
`,Sy=`# Dashboard layout for the Practicum Coordinator role at a Teacher Education / B.Ed. (ADR-0004 profile teacher-education-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: practicum-coordinator
title: "Practicum Coordinator"
widgets:
  - field-training.placements-open
  - field-training.active-placements
  - skill-progress.cohort-overview
  - placement-career.openings
`,_y=`# Dashboard layout for the Production Manager role at a Dance / Performing Arts Academy (ADR-0004 profile dance-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: production-manager
title: "Production Manager"
widgets:
  - productions.calendar
  - productions.upcoming
  - inventory-equipment.low-stock
  - facility-booking.bookings-today
`,by=`# Dashboard layout for the Production Supervisor role at a Film / Media / Animation Institute (ADR-0004 profile film-media-institute).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: production-supervisor
title: "Production Supervisor"
extends: faculty
widgets:
  - projects.to-review
  - projects.active
  - productions.in-preparation
  - selection-process.to-judge
`,Ey=`# Dashboard layout for the Project Guide role at a Engineering / Technology College (ADR-0004 profile engineering-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: project-guide
title: "Project Guide"
extends: faculty
widgets:
  - projects.to-review
  - projects.active
  - skill-progress.assessments-due
  - field-training.trainees-to-assess
`,Cy=`# Dashboard layout for the Research Lead role at a Agriculture / Veterinary / Field Sciences (ADR-0004 profile agriculture-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: research-lead
title: "Research Lead"
widgets:
  - projects.active
  - projects.to-review
  - productions.upcoming
  - field-training.placements-open
`,My=`# Dashboard layout for the Research Office role at a Research / Doctoral University (ADR-0004 profile research-university).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: research-office
title: "Research Office"
widgets:
  - selection-process.open-calls
  - projects.active
  - budget-grants.budget-vs-spend
  - productions.calendar
  - regulatory-reports.due
`,Ay=`# Dashboard layout for the Research Scholar role at a Research / Doctoral University (ADR-0004 profile research-university).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: research-scholar
title: "Research Scholar"
extends: student
widgets:
  - projects.my-projects
  - projects.milestones-due
  - portfolio.my-portfolio
  - productions.upcoming
  - selection-process.my-applications
  - budget-grants.my-grants
`,Ny=`# Dashboard layout for the Research Supervisor role at a Research / Doctoral University (ADR-0004 profile research-university).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: research-supervisor
title: "Research Supervisor"
extends: faculty
widgets:
  - projects.to-review
  - projects.active
  - selection-process.to-judge
  - portfolio.reviews-pending
`,Ty=`# Dashboard layout for the Stage Manager role at a Theatre / Drama Academy (ADR-0004 profile theatre-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: stage-manager
title: "Stage Manager"
widgets:
  - productions.calendar
  - facility-booking.bookings-today
  - inventory-equipment.low-stock
  - productions.upcoming
`,Iy=`# Dashboard layout for the Student role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: student
title: "Student"
widgets:
  - timetable-attendance.today
  - timetable-attendance.attendance-summary
  - examinations.upcoming-assessments
  - lms.course-materials
  - fees-accounts.fee-dues
  - hostel.notices
  - transport.notices
  - library.loans
`,Oy=`# Dashboard layout for the Studio Instructor role at a Arts Academy / Fine Arts College (ADR-0004 profile arts-academy).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: studio-instructor
title: "Studio Instructor"
extends: faculty
widgets:
  - portfolio.reviews-pending
  - projects.to-review
  - selection-process.to-judge
  - facility-booking.bookings-today
  - productions.in-preparation
`,Ly=`# Dashboard layout for the Super Admin, the platform operator outside every organisation (ADR-0005).
# Rendered by the admin screens in apps/frontend (one application, ADR-0005).
role: super-admin
title: "Super Admin"
widgets:
  - tenancy.approval-queue
  - tenancy.organisations-by-status
  - tenancy.recent-registrations
  - billing.trials-expiring
  - billing.revenue-by-plan
  - billing.subscriptions-by-plan
  - audit.super-admin-actions
`,Dy=`# Dashboard layout for the Support Staff (Helpdesk) role. Widget ids are <module>.<widget>.
# Order is display order. The shell hides widgets the viewer lacks permission for.
role: support-staff
title: "Support Staff (Helpdesk)"
widgets:
  - helpdesk.open-by-priority
  - sla-management.breaches
  - incident-management.open
  - amc-vendor-support.contracts-expiring
  - knowledge-base.top-articles
`,xy=`# Dashboard layout for the Teacher Trainee role at a Teacher Education / B.Ed. (ADR-0004 profile teacher-education-college).
# Widgets come from the generic practice, facilities and academics modules; the profile vocabulary names them.
role: teacher-trainee
title: "Teacher Trainee"
extends: student
widgets:
  - field-training.my-placement
  - projects.my-projects
  - portfolio.my-portfolio
  - skill-progress.my-progress
  - field-training.hours-logged
`,Ry=Object.assign({"../../../../platform/identity/config/dashboards/actor.yaml":Ig,"../../../../platform/identity/config/dashboards/applicant.yaml":Og,"../../../../platform/identity/config/dashboards/artist.yaml":Lg,"../../../../platform/identity/config/dashboards/athlete.yaml":Dg,"../../../../platform/identity/config/dashboards/chef-instructor.yaml":xg,"../../../../platform/identity/config/dashboards/choreographer.yaml":Rg,"../../../../platform/identity/config/dashboards/clinical-supervisor.yaml":Pg,"../../../../platform/identity/config/dashboards/coach.yaml":jg,"../../../../platform/identity/config/dashboards/corporate-mentor.yaml":$g,"../../../../platform/identity/config/dashboards/dancer.yaml":Fg,"../../../../platform/identity/config/dashboards/department-admin.yaml":zg,"../../../../platform/identity/config/dashboards/design-mentor.yaml":Bg,"../../../../platform/identity/config/dashboards/designer.yaml":Hg,"../../../../platform/identity/config/dashboards/director.yaml":Vg,"../../../../platform/identity/config/dashboards/engineering-student.yaml":Ug,"../../../../platform/identity/config/dashboards/ensemble-director.yaml":Kg,"../../../../platform/identity/config/dashboards/equipment-manager.yaml":Wg,"../../../../platform/identity/config/dashboards/examination-staff.yaml":qg,"../../../../platform/identity/config/dashboards/exhibition-manager.yaml":Qg,"../../../../platform/identity/config/dashboards/facility-staff.yaml":Gg,"../../../../platform/identity/config/dashboards/faculty.yaml":Yg,"../../../../platform/identity/config/dashboards/farm-supervisor.yaml":Jg,"../../../../platform/identity/config/dashboards/field-trainee.yaml":Xg,"../../../../platform/identity/config/dashboards/filmmaker.yaml":Zg,"../../../../platform/identity/config/dashboards/finance-staff.yaml":ey,"../../../../platform/identity/config/dashboards/governance.yaml":ty,"../../../../platform/identity/config/dashboards/hospital-coordinator.yaml":ny,"../../../../platform/identity/config/dashboards/hospitality-trainee.yaml":iy,"../../../../platform/identity/config/dashboards/hr-staff.yaml":ry,"../../../../platform/identity/config/dashboards/industry-coordinator.yaml":sy,"../../../../platform/identity/config/dashboards/industry-liaison.yaml":oy,"../../../../platform/identity/config/dashboards/lab-in-charge.yaml":ay,"../../../../platform/identity/config/dashboards/law-student.yaml":ly,"../../../../platform/identity/config/dashboards/legal-mentor.yaml":cy,"../../../../platform/identity/config/dashboards/management-student.yaml":uy,"../../../../platform/identity/config/dashboards/management.yaml":fy,"../../../../platform/identity/config/dashboards/medical-staff.yaml":dy,"../../../../platform/identity/config/dashboards/medical-student.yaml":py,"../../../../platform/identity/config/dashboards/mentor-teacher.yaml":hy,"../../../../platform/identity/config/dashboards/moot-court-coordinator.yaml":my,"../../../../platform/identity/config/dashboards/music-teacher.yaml":gy,"../../../../platform/identity/config/dashboards/musician.yaml":yy,"../../../../platform/identity/config/dashboards/nutritionist.yaml":vy,"../../../../platform/identity/config/dashboards/org-admin.yaml":wy,"../../../../platform/identity/config/dashboards/placement-officer.yaml":ky,"../../../../platform/identity/config/dashboards/practicum-coordinator.yaml":Sy,"../../../../platform/identity/config/dashboards/production-manager.yaml":_y,"../../../../platform/identity/config/dashboards/production-supervisor.yaml":by,"../../../../platform/identity/config/dashboards/project-guide.yaml":Ey,"../../../../platform/identity/config/dashboards/research-lead.yaml":Cy,"../../../../platform/identity/config/dashboards/research-office.yaml":My,"../../../../platform/identity/config/dashboards/research-scholar.yaml":Ay,"../../../../platform/identity/config/dashboards/research-supervisor.yaml":Ny,"../../../../platform/identity/config/dashboards/stage-manager.yaml":Ty,"../../../../platform/identity/config/dashboards/student.yaml":Iy,"../../../../platform/identity/config/dashboards/studio-instructor.yaml":Oy,"../../../../platform/identity/config/dashboards/super-admin.yaml":Ly,"../../../../platform/identity/config/dashboards/support-staff.yaml":Dy,"../../../../platform/identity/config/dashboards/teacher-trainee.yaml":xy});function p0(){var t;const e={};for(const[n,i]of Object.entries(Ry)){const r=_l(i),s=(t=n.split("/").pop())==null?void 0:t.replace(/\.yaml$/,"");if(r.role!==s)throw new Error(`Layout file ${n} declares role "${r.role}"; file name says "${s}"`);e[r.role]=r}return e}function h0(e,t){const n=t[e];if(!n)return[];const i=[];if(n.extends){const r=t[n.extends];if(!r)throw new Error(`Layout "${e}" extends unknown role "${n.extends}"`);if(r.extends)throw new Error(`Layout "${e}" extends "${n.extends}", which itself extends; only one level is allowed`);i.push(...r.widgets)}return i.push(...n.widgets),[...new Set(i)]}const Py=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: agriculture-college
title: "Agriculture / Veterinary / Field Sciences"
description: "Field training, farm management, practical rotations, labs, research trials, extension."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,          title: "Applicant" }
  - { id: student,            title: "Student" }
  - { id: field-trainee,      title: "Field Trainee" }
  - { id: faculty,            title: "Faculty / Instructor" }
  - { id: farm-supervisor,    title: "Farm Supervisor" }
  - { id: research-lead,      title: "Research Lead" }
  - { id: examination-staff,  title: "Examination Staff" }
  - { id: department-admin,   title: "Department Admin / HoD" }
  - { id: finance-staff,      title: "Finance Staff" }
  - { id: hr-staff,           title: "HR Staff" }
  - { id: facility-staff,     title: "Facility / Inventory Staff" }
  - { id: governance,         title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,      title: "Support Staff (Helpdesk)" }
  - { id: management,         title: "Management (VC, Registrar)" }
  - { id: org-admin,          title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  field-training.placement: "Farm / practical rotation"
  projects.project: "Research trial"
  facility-booking.resource: "Farm plot / lab"
  productions.production: "Extension activity"
`,jy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: arts-academy
title: "Arts Academy / Fine Arts College"
description: "Studios, portfolios, artwork projects, critiques and juries, exhibitions."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,           title: "Applicant" }
  - { id: student,             title: "Student" }
  - { id: artist,              title: "Artist" }
  - { id: faculty,             title: "Faculty / Instructor" }
  - { id: studio-instructor,   title: "Studio Instructor" }
  - { id: exhibition-manager,  title: "Exhibition & Gallery Manager" }
  - { id: examination-staff,   title: "Examination Staff" }
  - { id: department-admin,    title: "Department Admin / HoD" }
  - { id: finance-staff,       title: "Finance Staff" }
  - { id: hr-staff,            title: "HR Staff" }
  - { id: facility-staff,      title: "Facility / Inventory Staff" }
  - { id: governance,          title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,       title: "Support Staff (Helpdesk)" }
  - { id: management,          title: "Management (VC, Registrar)" }
  - { id: org-admin,           title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  portfolio.item: "Artwork"
  projects.project: "Artwork project"
  selection-process.selection: "Critique / jury"
  productions.production: "Exhibition"
  facility-booking.resource: "Studio"
  inventory-equipment.item: "Material"
`,$y=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: dance-academy
title: "Dance / Performing Arts Academy"
description: "Classes, choreography, studios, auditions, performances, costumes and skill progress."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,           title: "Applicant" }
  - { id: student,             title: "Student" }
  - { id: dancer,              title: "Dancer" }
  - { id: faculty,             title: "Faculty / Instructor" }
  - { id: choreographer,       title: "Choreographer" }
  - { id: production-manager,  title: "Production Manager" }
  - { id: examination-staff,   title: "Examination Staff" }
  - { id: department-admin,    title: "Department Admin / HoD" }
  - { id: finance-staff,       title: "Finance Staff" }
  - { id: hr-staff,            title: "HR Staff" }
  - { id: facility-staff,      title: "Facility / Inventory Staff" }
  - { id: governance,          title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,       title: "Support Staff (Helpdesk)" }
  - { id: management,          title: "Management (VC, Registrar)" }
  - { id: org-admin,           title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  productions.production: "Performance"
  selection-process.selection: "Audition"
  facility-booking.resource: "Practice studio"
  inventory-equipment.item: "Costume / prop"
  skill-progress.assessment: "Technique assessment"
`,Fy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: design-fashion-institute
title: "Design / Fashion Institute"
description: "Design studios, collections, critiques, shows, industry projects and internships."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,          title: "Applicant" }
  - { id: student,            title: "Student" }
  - { id: designer,           title: "Designer" }
  - { id: faculty,            title: "Faculty / Instructor" }
  - { id: design-mentor,      title: "Design Mentor" }
  - { id: industry-liaison,   title: "Industry Liaison" }
  - { id: examination-staff,  title: "Examination Staff" }
  - { id: department-admin,   title: "Department Admin / HoD" }
  - { id: finance-staff,      title: "Finance Staff" }
  - { id: hr-staff,           title: "HR Staff" }
  - { id: facility-staff,     title: "Facility / Inventory Staff" }
  - { id: governance,         title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,      title: "Support Staff (Helpdesk)" }
  - { id: management,         title: "Management (VC, Registrar)" }
  - { id: org-admin,          title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  portfolio.item: "Collection"
  projects.project: "Collection / industry project"
  selection-process.selection: "Critique"
  productions.production: "Show"
  facility-booking.resource: "Studio"
  field-training.placement: "Internship"
`,zy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: engineering-college
title: "Engineering / Technology College"
description: "Labs, capstone projects, industrial training, innovation, hackathons, placements."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,            title: "Applicant" }
  - { id: student,              title: "Student" }
  - { id: engineering-student,  title: "Engineering Student" }
  - { id: faculty,              title: "Faculty / Instructor" }
  - { id: project-guide,        title: "Project Guide" }
  - { id: lab-in-charge,        title: "Lab In-charge" }
  - { id: examination-staff,    title: "Examination Staff" }
  - { id: department-admin,     title: "Department Admin / HoD" }
  - { id: finance-staff,        title: "Finance Staff" }
  - { id: hr-staff,             title: "HR Staff" }
  - { id: facility-staff,       title: "Facility / Inventory Staff" }
  - { id: governance,           title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,        title: "Support Staff (Helpdesk)" }
  - { id: management,           title: "Management (VC, Registrar)" }
  - { id: org-admin,            title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  projects.project: "Capstone / project"
  facility-booking.resource: "Laboratory"
  productions.production: "Hackathon / tech event"
  field-training.placement: "Industrial training"
  inventory-equipment.item: "Lab equipment"
`,By=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: film-media-institute
title: "Film / Media / Animation Institute"
description: "Film projects, production, equipment, media assets, editing, screenings and showreels."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,              title: "Applicant" }
  - { id: student,                title: "Student" }
  - { id: filmmaker,              title: "Filmmaker" }
  - { id: faculty,                title: "Faculty / Instructor" }
  - { id: production-supervisor,  title: "Production Supervisor" }
  - { id: equipment-manager,      title: "Equipment Manager" }
  - { id: examination-staff,      title: "Examination Staff" }
  - { id: department-admin,       title: "Department Admin / HoD" }
  - { id: finance-staff,          title: "Finance Staff" }
  - { id: hr-staff,               title: "HR Staff" }
  - { id: facility-staff,         title: "Facility / Inventory Staff" }
  - { id: governance,             title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,          title: "Support Staff (Helpdesk)" }
  - { id: management,             title: "Management (VC, Registrar)" }
  - { id: org-admin,              title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  projects.project: "Film project"
  portfolio.item: "Showreel"
  productions.production: "Screening / festival"
  inventory-equipment.item: "Equipment"
  facility-booking.resource: "Edit suite / studio"
`,Hy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: hospitality-institute
title: "Hospitality / Hotel Management"
description: "Training kitchens, hotel operations, internships, practical assessments, events."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,             title: "Applicant" }
  - { id: student,               title: "Student" }
  - { id: hospitality-trainee,   title: "Hospitality Trainee" }
  - { id: faculty,               title: "Faculty / Instructor" }
  - { id: chef-instructor,       title: "Chef / Operations Instructor" }
  - { id: industry-coordinator,  title: "Industry Coordinator" }
  - { id: examination-staff,     title: "Examination Staff" }
  - { id: department-admin,      title: "Department Admin / HoD" }
  - { id: finance-staff,         title: "Finance Staff" }
  - { id: hr-staff,              title: "HR Staff" }
  - { id: facility-staff,        title: "Facility / Inventory Staff" }
  - { id: governance,            title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,         title: "Support Staff (Helpdesk)" }
  - { id: management,            title: "Management (VC, Registrar)" }
  - { id: org-admin,             title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  field-training.placement: "Industry internship"
  facility-booking.resource: "Training kitchen / lab"
  productions.production: "Banquet / event"
  skill-progress.assessment: "Practical assessment"
`,Vy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: law-college
title: "Law College / Law University"
description: "Moot court, internships, case research, legal clinics, competitions, court visits."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,               title: "Applicant" }
  - { id: student,                 title: "Student" }
  - { id: law-student,             title: "Law Student" }
  - { id: faculty,                 title: "Faculty / Instructor" }
  - { id: legal-mentor,            title: "Legal Mentor" }
  - { id: moot-court-coordinator,  title: "Moot Court Coordinator" }
  - { id: examination-staff,       title: "Examination Staff" }
  - { id: department-admin,        title: "Department Admin / HoD" }
  - { id: finance-staff,           title: "Finance Staff" }
  - { id: hr-staff,                title: "HR Staff" }
  - { id: facility-staff,          title: "Facility / Inventory Staff" }
  - { id: governance,              title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,           title: "Support Staff (Helpdesk)" }
  - { id: management,              title: "Management (VC, Registrar)" }
  - { id: org-admin,               title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  selection-process.selection: "Moot court selection"
  productions.production: "Competition / debate"
  field-training.placement: "Legal internship / clinic"
  projects.project: "Case research"
`,Uy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: management-institute
title: "Management / Business School"
description: "Case competitions, corporate relations, live projects, internships, placements, alumni."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,           title: "Applicant" }
  - { id: student,             title: "Student" }
  - { id: management-student,  title: "Management Student" }
  - { id: faculty,             title: "Faculty / Instructor" }
  - { id: corporate-mentor,    title: "Corporate Mentor" }
  - { id: placement-officer,   title: "Placement Officer" }
  - { id: examination-staff,   title: "Examination Staff" }
  - { id: department-admin,    title: "Department Admin / HoD" }
  - { id: finance-staff,       title: "Finance Staff" }
  - { id: hr-staff,            title: "HR Staff" }
  - { id: facility-staff,      title: "Facility / Inventory Staff" }
  - { id: governance,          title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,       title: "Support Staff (Helpdesk)" }
  - { id: management,          title: "Management (VC, Registrar)" }
  - { id: org-admin,           title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  productions.production: "Case competition / industry event"
  projects.project: "Live project"
  field-training.placement: "Internship"
  selection-process.selection: "Competition selection"
`,Ky=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: medical-college
title: "Medical / Health Sciences College"
description: "Clinical training and rotations, skills, hospital integration, labs, residency, research."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,             title: "Applicant" }
  - { id: student,               title: "Student" }
  - { id: medical-student,       title: "Medical Student" }
  - { id: faculty,               title: "Faculty / Instructor" }
  - { id: clinical-supervisor,   title: "Clinical Supervisor" }
  - { id: hospital-coordinator,  title: "Hospital Coordinator" }
  - { id: examination-staff,     title: "Examination Staff" }
  - { id: department-admin,      title: "Department Admin / HoD" }
  - { id: finance-staff,         title: "Finance Staff" }
  - { id: hr-staff,              title: "HR Staff" }
  - { id: facility-staff,        title: "Facility / Inventory Staff" }
  - { id: governance,            title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,         title: "Support Staff (Helpdesk)" }
  - { id: management,            title: "Management (VC, Registrar)" }
  - { id: org-admin,             title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  field-training.placement: "Clinical rotation"
  skill-progress.assessment: "Skills assessment"
  facility-booking.resource: "Lab / skills room"
  projects.project: "Research project"
`,Wy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: music-academy
title: "Music Academy / Conservatory"
description: "Lessons, practice rooms, auditions, recitals, ensembles and instruments."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,          title: "Applicant" }
  - { id: student,            title: "Student" }
  - { id: musician,           title: "Musician" }
  - { id: faculty,            title: "Faculty / Instructor" }
  - { id: music-teacher,      title: "Music Teacher" }
  - { id: ensemble-director,  title: "Ensemble / Orchestra Director" }
  - { id: examination-staff,  title: "Examination Staff" }
  - { id: department-admin,   title: "Department Admin / HoD" }
  - { id: finance-staff,      title: "Finance Staff" }
  - { id: hr-staff,           title: "HR Staff" }
  - { id: facility-staff,     title: "Facility / Inventory Staff" }
  - { id: governance,         title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,      title: "Support Staff (Helpdesk)" }
  - { id: management,         title: "Management (VC, Registrar)" }
  - { id: org-admin,          title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  portfolio.item: "Repertoire piece"
  selection-process.selection: "Audition"
  productions.production: "Recital / concert"
  facility-booking.resource: "Practice room"
  inventory-equipment.item: "Instrument"
  skill-progress.assessment: "Grade exam"
`,qy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: research-university
title: "Research / Doctoral University"
description: "PhD lifecycle, supervisors, proposals, ethics, grants, publications, conferences, viva."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,            title: "Applicant" }
  - { id: student,              title: "Student" }
  - { id: research-scholar,     title: "Research Scholar" }
  - { id: faculty,              title: "Faculty / Instructor" }
  - { id: research-supervisor,  title: "Research Supervisor" }
  - { id: research-office,      title: "Research Office" }
  - { id: examination-staff,    title: "Examination Staff" }
  - { id: department-admin,     title: "Department Admin / HoD" }
  - { id: finance-staff,        title: "Finance Staff" }
  - { id: hr-staff,             title: "HR Staff" }
  - { id: facility-staff,       title: "Facility / Inventory Staff" }
  - { id: governance,           title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,        title: "Support Staff (Helpdesk)" }
  - { id: management,           title: "Management (VC, Registrar)" }
  - { id: org-admin,            title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  projects.project: "Research project"
  portfolio.item: "Publication"
  productions.production: "Conference"
  selection-process.selection: "Supervisor allocation / viva"
  projects.milestone: "Thesis milestone"
`,Qy=`# Institution profile: everything one installation of Education OS enables.
# Decision and format: docs/architecture/adr/0004-institution-profiles.md
# Apps read modules.enabled from here; the gateway blocks routes of modules not listed.
profile: sports-college
title: "Sports University / Sports College"
description: "Reference profile. Common suites plus the sports specialization."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: [sports]

# <domain>/<module> under modules/. Everything not listed is disabled, in the UI and at the API.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - sports/athlete-performance
  - sports/training-video-analysis
  - sports/sports-nutrition-health
  - sports/tournament-events
  - facilities/sports-facilities
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - wearables
  - external-university-portals

# Roles for this institution. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,          title: "Applicant" }
  - { id: student,            title: "Student" }
  - { id: athlete,            title: "Athlete" }
  - { id: faculty,            title: "Faculty / Instructor" }
  - { id: coach,              title: "Coach" }
  - { id: medical-staff,      title: "Medical Staff (Doctor / Physio)" }
  - { id: nutritionist,       title: "Nutritionist" }
  - { id: examination-staff,  title: "Examination Staff" }
  - { id: department-admin,   title: "Department Admin / HoD" }
  - { id: finance-staff,      title: "Finance Staff" }
  - { id: hr-staff,           title: "HR Staff" }
  - { id: facility-staff,     title: "Facility / Inventory Staff" }
  - { id: governance,         title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,      title: "Support Staff (Helpdesk)" }
  - { id: management,         title: "Management (VC, Registrar)" }
  - { id: org-admin,          title: "Organisation Admin" }     # created at registration (ADR-0005)

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this institution uses.
vocabulary:
  facility-booking.resource: "Facility"
  facility-booking.resources: "Facilities"
  inventory-equipment.item: "Equipment"
  tournament-events.event: "Tournament"
  athlete-performance.subject: "Athlete"
`,Gy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: teacher-education-college
title: "Teacher Education / B.Ed."
description: "Teaching practice, school internships, lesson plans, observation, portfolios, mentors."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,              title: "Applicant" }
  - { id: student,                title: "Student" }
  - { id: teacher-trainee,        title: "Teacher Trainee" }
  - { id: faculty,                title: "Faculty / Instructor" }
  - { id: mentor-teacher,         title: "Mentor Teacher" }
  - { id: practicum-coordinator,  title: "Practicum Coordinator" }
  - { id: examination-staff,      title: "Examination Staff" }
  - { id: department-admin,       title: "Department Admin / HoD" }
  - { id: finance-staff,          title: "Finance Staff" }
  - { id: hr-staff,               title: "HR Staff" }
  - { id: facility-staff,         title: "Facility / Inventory Staff" }
  - { id: governance,             title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,          title: "Support Staff (Helpdesk)" }
  - { id: management,             title: "Management (VC, Registrar)" }
  - { id: org-admin,              title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  field-training.placement: "School internship"
  projects.project: "Lesson plan"
  portfolio.item: "Teaching portfolio"
  skill-progress.assessment: "Practicum assessment"
`,Yy=`# Institution profile: everything one organisation of this academy type enables (ADR-0004, ADR-0005).
# Chosen at registration as the academy type. The plan then decides how much of it is unlocked.
profile: theatre-academy
title: "Theatre / Drama Academy"
description: "Productions, casting, rehearsals, scripts, stage and venue, costumes and tickets."

suites:
  common: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
  specialized: []

# <domain>/<module> under modules/. Field-specific behaviour comes from the practice suite plus vocabulary.
modules:
  - student-lifecycle/web-portal-cms
  - student-lifecycle/admissions
  - student-lifecycle/student-information
  - student-lifecycle/enrolment-registration
  - academics/academic-management
  - academics/lms
  - academics/examinations
  - academics/timetable-attendance
  - practice/portfolio
  - practice/projects
  - practice/selection-process
  - practice/productions
  - practice/field-training
  - practice/skill-progress
  - facilities/facility-booking
  - facilities/inventory-equipment
  - facilities/asset-management
  - facilities/maintenance
  - finance-operations/fees-accounts
  - finance-operations/budget-grants
  - finance-operations/procurement
  - finance-operations/hr-payroll
  - finance-operations/e-office
  - campus-life/hostel
  - campus-life/transport
  - campus-life/library
  - campus-life/placement-career
  - campus-life/alumni
  - governance/grievance
  - governance/rti
  - governance/iqac-accreditation
  - governance/regulatory-reports
  - support/helpdesk
  - support/sla-management
  - support/knowledge-base
  - support/incident-management
  - support/amc-vendor-support

integrations:
  - payment-sbiepay
  - digilocker
  - nad
  - government-portals
  - messaging-providers
  - video-conferencing
  - external-university-portals

# Roles for this academy. id = dashboard layout file in ../dashboards/<id>.yaml.
roles:
  - { id: applicant,          title: "Applicant" }
  - { id: student,            title: "Student" }
  - { id: actor,              title: "Actor" }
  - { id: faculty,            title: "Faculty / Instructor" }
  - { id: director,           title: "Director" }
  - { id: stage-manager,      title: "Stage Manager" }
  - { id: examination-staff,  title: "Examination Staff" }
  - { id: department-admin,   title: "Department Admin / HoD" }
  - { id: finance-staff,      title: "Finance Staff" }
  - { id: hr-staff,           title: "HR Staff" }
  - { id: facility-staff,     title: "Facility / Inventory Staff" }
  - { id: governance,         title: "Governance (Grievance / RTI / IQAC)" }
  - { id: support-staff,      title: "Support Staff (Helpdesk)" }
  - { id: management,         title: "Management (VC, Registrar)" }
  - { id: org-admin,          title: "Organisation Admin" }

# Field vocabulary for generic modules. Key = <module>.<term>, value = the word this academy uses.
vocabulary:
  productions.production: "Production"
  selection-process.selection: "Casting call"
  facility-booking.resource: "Rehearsal space / venue"
  inventory-equipment.item: "Costume / prop"
  projects.project: "Script"
`,Jy=`# Plans. The super admin edits these in the admin screens of apps/frontend; this file is the seed and the default.
# An organisation's entitlement = modules in its academy profile that its plan allows,
# plus super-admin overrides. "suites" and "modules" accept suite names (every module in the
# suite) or <domain>/<module> paths. "*" means everything.
plans:
  - id: trial
    title: "Trial"
    description: "Try the common platform and one specialized suite, free for 30 days."
    trial_days: 30
    price_per_month: 0
    currency: INR
    suites: [student-lifecycle, academics, practice, support]
    modules: []
    specialized_suites: 1        # how many of the profile's specialized suites are on
    integrations: [messaging-providers]
    limits: { users: 25, students: 500, storage_gb: 2 }
    after_trial: read_only       # read_only | suspend

  - id: standard
    title: "Standard"
    description: "Every common suite plus the profile's specialized suites."
    price_per_month: 24999
    currency: INR
    suites: [student-lifecycle, academics, practice, facilities, finance-operations, campus-life, governance, support]
    modules: []
    specialized_suites: all
    integrations: [messaging-providers, payment-sbiepay, video-conferencing, digilocker]
    limits: { users: 500, students: 10000, storage_gb: 100 }

  - id: premium
    title: "Premium"
    description: "Everything, every integration, priority support."
    price_per_month: 59999
    currency: INR
    suites: ["*"]
    modules: []
    specialized_suites: all
    integrations: ["*"]
    limits: { users: 5000, students: 100000, storage_gb: 1000 }
    support: priority
`,Xy=Object.assign({"../../../../platform/identity/config/profiles/agriculture-college.yaml":Py,"../../../../platform/identity/config/profiles/arts-academy.yaml":jy,"../../../../platform/identity/config/profiles/dance-academy.yaml":$y,"../../../../platform/identity/config/profiles/design-fashion-institute.yaml":Fy,"../../../../platform/identity/config/profiles/engineering-college.yaml":zy,"../../../../platform/identity/config/profiles/film-media-institute.yaml":By,"../../../../platform/identity/config/profiles/hospitality-institute.yaml":Hy,"../../../../platform/identity/config/profiles/law-college.yaml":Vy,"../../../../platform/identity/config/profiles/management-institute.yaml":Uy,"../../../../platform/identity/config/profiles/medical-college.yaml":Ky,"../../../../platform/identity/config/profiles/music-academy.yaml":Wy,"../../../../platform/identity/config/profiles/research-university.yaml":qy,"../../../../platform/identity/config/profiles/sports-college.yaml":Qy,"../../../../platform/identity/config/profiles/teacher-education-college.yaml":Gy,"../../../../platform/identity/config/profiles/theatre-academy.yaml":Yy}),Zy=Object.assign({"../../../../platform/billing/config/plans.yaml":Jy});function m0(){const e={};for(const t of Object.values(Xy)){const n=_l(t);e[n.profile]=n}return e}function g0(){const e=Object.values(Zy)[0];if(!e)return{};const t=_l(e);return Object.fromEntries(t.plans.map(n=>[n.id,n]))}const e0=e=>e.split("/")[0]??"",t0=e=>e.split("/").pop()??e;function y0(e,t,n=[]){const i=t.suites.includes("*"),r=new Set(t.specialized_suites==="all"?e.suites.specialized:e.suites.specialized.slice(0,t.specialized_suites)),s=l=>{const c=e0(l);return t.modules.includes(l)?!0:e.suites.specialized.includes(c)?i||r.has(c):i||t.suites.includes(c)},o=e.modules.filter(l=>s(l)||n.includes(l)),a=e.modules.filter(l=>!o.includes(l));return{plan:t.id,academyType:e.profile,modules:new Set(o),moduleNames:new Set(o.map(t0)),upgradableModules:a,limits:t.limits}}function v0(e){return e.split(".")[0]??e}const n0=[{id:"org-admin",title:"Organisation Admin"},{id:"super-admin",title:"Super Admin (platform operator)"}];function w0(e){const t=new Set(e.map(n=>n.id));return[...e,...n0.filter(n=>!t.has(n.id))]}const i0=e=>Object.keys(e).some(t=>t.startsWith("aria-")||t==="role"||t==="title");function b(e,t){const n=Kt.forwardRef(({color:i,size:r,width:s,height:o,strokeWidth:a,absoluteStrokeWidth:l,className:c="",children:h,...u},p)=>{const g=s??r??24,v=o??r??24,y=l?Number(a??2)*24/Number(r??s??24):a??2,k=["lucide",`lucide-${e}`,...c.split(" ")].filter((d,f,m)=>d.trim()!==""&&m.indexOf(d)===f);return Kt.createElement("svg",{ref:p,xmlns:"http://www.w3.org/2000/svg",width:g,height:v,viewBox:"0 0 24 24",fill:"none",stroke:i||"currentColor",strokeWidth:y,strokeLinecap:"round",strokeLinejoin:"round",className:k.join(" "),...h||i0(u)?{}:{"aria-hidden":"true"},...u},...t.map(([d,f],m)=>Kt.createElement(d,{key:m,...f})),h)});return n.displayName=e,n}b("activity",[["path",{d:"M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"}]]);const r0=b("triangle-alert",[["path",{d:"m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"}],["path",{d:"M12 9v4"}],["path",{d:"M12 17h.01"}]]);b("apple",[["path",{d:"M12 6.528V3a1 1 0 0 1 1-1h0"}],["path",{d:"M18.237 21A15 15 0 0 0 22 11a6 6 0 0 0-10-4.472A6 6 0 0 0 2 11a15.1 15.1 0 0 0 3.763 10 3 3 0 0 0 3.648.648 5.5 5.5 0 0 1 5.178 0A3 3 0 0 0 18.237 21"}]]);const k0=b("arrow-right",[["path",{d:"M5 12h14"}],["path",{d:"m12 5 7 7-7 7"}]]);b("award",[["path",{d:"m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"}],["circle",{cx:"12",cy:"8",r:"6"}]]);b("badge-check",[["path",{d:"M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"}],["path",{d:"m16 9-5.5 5.5L8 12"}]]);const S0=b("bell",[["path",{d:"M10.268 21a2 2 0 0 0 3.464 0"}],["path",{d:"M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"}]]),_0=b("blocks",[["path",{d:"M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2"}],["rect",{x:"14",y:"2",width:"8",height:"8",rx:"1"}]]);b("book-bookmark",[["path",{d:"M10 2v7.751a.25.25 0 00.407.195l2.28-1.834a.5.5 0 01.627 0l2.28 1.834A.25.25 0 0016 9.751V2"}],["path",{d:"M4 19.5v-15A2.5 2.5 0 016.5 2H19a1 1 0 011 1v18a1 1 0 01-1 1H6.5a1 1 0 010-5H20"}]]);const b0=b("book-open",[["path",{d:"M12 5v16"}],["path",{d:"M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z"}]]);b("boxes",[["path",{d:"M2.97 12.92A2 2 0 0 0 2 14.63v3.24a2 2 0 0 0 .97 1.71l3 1.8a2 2 0 0 0 2.06 0L12 19v-5.5l-5-3-4.03 2.42Z"}],["path",{d:"m7 16.5-4.74-2.85"}],["path",{d:"m7 16.5 5-3"}],["path",{d:"M7 16.5v5.17"}],["path",{d:"M12 13.5V19l3.97 2.38a2 2 0 0 0 2.06 0l3-1.8a2 2 0 0 0 .97-1.71v-3.24a2 2 0 0 0-.97-1.71L17 10.5l-5 3Z"}],["path",{d:"m17 16.5-5-3"}],["path",{d:"m17 16.5 4.74-2.85"}],["path",{d:"M17 16.5v5.17"}],["path",{d:"M7.97 4.42A2 2 0 0 0 7 6.13v4.37l5 3 5-3V6.13a2 2 0 0 0-.97-1.71l-3-1.8a2 2 0 0 0-2.06 0l-3 1.8Z"}],["path",{d:"M12 8 7.26 5.15"}],["path",{d:"m12 8 4.74-2.85"}],["path",{d:"M12 13.5V8"}]]);b("briefcase",[["path",{d:"M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"}],["rect",{width:"20",height:"14",x:"2",y:"6",rx:"2"}]]);b("building",[["path",{d:"M12 10h.01"}],["path",{d:"M12 14h.01"}],["path",{d:"M12 6h.01"}],["path",{d:"M16 10h.01"}],["path",{d:"M16 14h.01"}],["path",{d:"M16 6h.01"}],["path",{d:"M8 10h.01"}],["path",{d:"M8 14h.01"}],["path",{d:"M8 6h.01"}],["path",{d:"M9 22v-3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3"}],["rect",{x:"4",y:"2",width:"16",height:"20",rx:"2"}]]);const E0=b("building-complex",[["path",{d:"M10 12h4"}],["path",{d:"M10 8h4"}],["path",{d:"M14 21v-3a2 2 0 0 0-4 0v3"}],["path",{d:"M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2"}],["path",{d:"M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"}]]);b("bus",[["path",{d:"M8 6v6"}],["path",{d:"M15 6v6"}],["path",{d:"M2 12h19.6"}],["path",{d:"M18 18h3s.5-1.7.8-2.8c.1-.4.2-.8.2-1.2 0-.4-.1-.8-.2-1.2l-1.4-5C20.1 6.8 19.1 6 18 6H4a2 2 0 0 0-2 2v10h3"}],["circle",{cx:"7",cy:"18",r:"2"}],["path",{d:"M9 18h5"}],["circle",{cx:"16",cy:"18",r:"2"}]]);b("calendar-check-2",[["path",{d:"M 19 3 L 5 3"}],["path",{d:"M 21 13 L 21 5"}],["path",{d:"M 21 5 A2 2 0 0 0 19 3"}],["path",{d:"M 3 19 A2 2 0 0 0 5 21"}],["path",{d:"M 3 5 L 3 19"}],["path",{d:"M 5 3 A2 2 0 0 0 3 5"}],["path",{d:"m16 19 2 2 4-4"}],["path",{d:"M16 2v3"}],["path",{d:"M3 9h18"}],["path",{d:"M5 21 L12.5 21"}],["path",{d:"M8 2v3"}]]);b("calendar-range",[["rect",{x:"3",y:"3",width:"18",height:"18",rx:"2"}],["path",{d:"M16 2v3"}],["path",{d:"M3 9h18"}],["path",{d:"M8 2v3"}],["path",{d:"M17 13h-6"}],["path",{d:"M13 17H7"}],["path",{d:"M7 13h.01"}],["path",{d:"M17 17h.01"}]]);b("check",[["path",{d:"M20 6 9 17l-5-5"}]]);b("circle-check",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m16 9-5.5 5.5L8 12"}]]);const C0=b("chevron-down",[["path",{d:"m6 9 6 6 6-6"}]]),M0=b("chevron-left",[["path",{d:"m15 18-6-6 6-6"}]]),A0=b("chevron-right",[["path",{d:"m9 18 6-6-6-6"}]]);b("clipboard-list",[["rect",{width:"8",height:"4",x:"8",y:"2",rx:"1",ry:"1"}],["path",{d:"M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"}],["path",{d:"M12 11h4"}],["path",{d:"M12 16h4"}],["path",{d:"M8 11h.01"}],["path",{d:"M8 16h.01"}]]);b("clock",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M12 6v6l4 2"}]]);b("cpu",[["path",{d:"M12 20v2"}],["path",{d:"M12 2v2"}],["path",{d:"M17 20v2"}],["path",{d:"M17 2v2"}],["path",{d:"M2 12h2"}],["path",{d:"M2 17h2"}],["path",{d:"M2 7h2"}],["path",{d:"M20 12h2"}],["path",{d:"M20 17h2"}],["path",{d:"M20 7h2"}],["path",{d:"M7 20v2"}],["path",{d:"M7 2v2"}],["rect",{x:"4",y:"4",width:"16",height:"16",rx:"2"}],["rect",{x:"8",y:"8",width:"8",height:"8",rx:"1"}]]);b("credit-card",[["rect",{width:"20",height:"14",x:"2",y:"5",rx:"2"}],["line",{x1:"2",x2:"22",y1:"10",y2:"10"}],["path",{d:"M6 14h2"}]]);b("download",[["path",{d:"M12 15V3"}],["path",{d:"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}],["path",{d:"m7 10 5 5 5-5"}]]);b("cloud-download",[["path",{d:"M12 13v8l-4-4"}],["path",{d:"m12 21 4-4"}],["path",{d:"M4.393 15.269A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.436 8.284"}]]);b("dumbbell",[["path",{d:"M17.596 12.768a2 2 0 1 0 2.829-2.829l-1.768-1.767a2 2 0 0 0 2.828-2.829l-2.828-2.828a2 2 0 0 0-2.829 2.828l-1.767-1.768a2 2 0 1 0-2.829 2.829z"}],["path",{d:"m2.5 21.5 1.4-1.4"}],["path",{d:"m20.1 3.9 1.4-1.4"}],["path",{d:"M5.343 21.485a2 2 0 1 0 2.829-2.828l1.767 1.768a2 2 0 1 0 2.829-2.829l-6.364-6.364a2 2 0 1 0-2.829 2.829l1.768 1.767a2 2 0 0 0-2.828 2.829z"}],["path",{d:"m9.6 14.4 4.8-4.8"}]]);b("eye-off",[["path",{d:"M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"}],["path",{d:"M14.084 14.158a3 3 0 0 1-4.242-4.242"}],["path",{d:"M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"}],["path",{d:"m2 2 20 20"}]]);b("file-check-corner",[["path",{d:"M10.5 22H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v6"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"m14 20 2 2 4-4"}]]);b("file-clock",[["path",{d:"M16 22h2a2 2 0 0 0 2-2V8a2.4 2.4 0 0 0-.706-1.706l-3.588-3.588A2.4 2.4 0 0 0 14 2H6a2 2 0 0 0-2 2v2.85"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"M8 14v2.2l1.6 1"}],["circle",{cx:"8",cy:"16",r:"6"}]]);b("file-code-corner",[["path",{d:"M4 12.15V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.706.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2h-3.35"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"m5 16-3 3 3 3"}],["path",{d:"m9 22 3-3-3-3"}]]);b("file-text",[["path",{d:"M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z"}],["path",{d:"M14 2v5a1 1 0 0 0 1 1h5"}],["path",{d:"M10 9H8"}],["path",{d:"M16 13H8"}],["path",{d:"M16 17H8"}]]);b("folder-open",[["path",{d:"m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"}]]);b("globe",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"}],["path",{d:"M2 12h20"}]]);const N0=b("graduation-cap",[["path",{d:"M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"}],["path",{d:"M22 10v6"}],["path",{d:"M6 12.5V16a6 3 0 0 0 12 0v-3.5"}]]);b("hammer",[["path",{d:"m15 12-9.373 9.373a1 1 0 0 1-3.001-3L12 9"}],["path",{d:"m18 15 4-4"}],["path",{d:"m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172v-.344a2 2 0 0 0-.586-1.414l-1.657-1.657A6 6 0 0 0 12.516 3H9l1.243 1.243A6 6 0 0 1 12 8.485V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5"}]]);b("handshake",[["path",{d:"m11 17 2 2a1 1 0 1 0 3-3"}],["path",{d:"m14 14 2.5 2.5a1 1 0 1 0 3-3l-3.88-3.88a3 3 0 0 0-4.24 0l-.88.88a1 1 0 1 1-3-3l2.81-2.81a5.79 5.79 0 0 1 7.06-.87l.47.28a2 2 0 0 0 1.42.25L21 4"}],["path",{d:"m21 3 1 11h-2"}],["path",{d:"M3 3 2 14l6.5 6.5a1 1 0 1 0 3-3"}],["path",{d:"M3 4h8"}]]);const T0=b("circle-question-mark",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"}],["path",{d:"M12 17h.01"}]]);b("rotate-ccw-clock",[["path",{d:"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"}],["path",{d:"M3 3v5h5"}],["path",{d:"M12 7v5l4 2"}]]);const I0=b("house",[["path",{d:"M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"}],["path",{d:"M3 10a2 2 0 0 1 .709-1.528l7-6a2 2 0 0 1 2.582 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"}]]);b("indian-rupee",[["path",{d:"M6 3h12"}],["path",{d:"M6 8h12"}],["path",{d:"m6 13 8.5 8"}],["path",{d:"M6 13h3"}],["path",{d:"M9 13c6.667 0 6.667-10 0-10"}]]);b("key-round",[["path",{d:"M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"}],["circle",{cx:"16.5",cy:"7.5",r:".5",fill:"currentColor"}]]);const O0=b("landmark",[["path",{d:"M10 18v-7"}],["path",{d:"M11.119 2.205a2 2 0 0 1 1.762 0l7.84 3.846A.5.5 0 0 1 20.5 7h-17a.5.5 0 0 1-.22-.949z"}],["path",{d:"M14 18v-7"}],["path",{d:"M18 18v-7"}],["path",{d:"M3 22h18"}],["path",{d:"M6 18v-7"}]]);b("layers",[["path",{d:"M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"}],["path",{d:"M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"}],["path",{d:"M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"}]]);const L0=b("layout-dashboard",[["rect",{width:"7",height:"9",x:"3",y:"3",rx:"1"}],["rect",{width:"7",height:"5",x:"14",y:"3",rx:"1"}],["rect",{width:"7",height:"9",x:"14",y:"12",rx:"1"}],["rect",{width:"7",height:"5",x:"3",y:"16",rx:"1"}]]);b("layout-grid",[["rect",{width:"7",height:"7",x:"3",y:"3",rx:"1"}],["rect",{width:"7",height:"7",x:"14",y:"3",rx:"1"}],["rect",{width:"7",height:"7",x:"14",y:"14",rx:"1"}],["rect",{width:"7",height:"7",x:"3",y:"14",rx:"1"}]]);b("library",[["path",{d:"m16 6 4 14"}],["path",{d:"M12 6v14"}],["path",{d:"M8 8v12"}],["path",{d:"M4 4v16"}]]);const D0=b("life-buoy",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m4.93 4.93 4.24 4.24"}],["path",{d:"m14.83 9.17 4.24-4.24"}],["path",{d:"m14.83 14.83 4.24 4.24"}],["path",{d:"m9.17 14.83-4.24 4.24"}],["circle",{cx:"12",cy:"12",r:"4"}]]),x0=b("lock",[["rect",{width:"18",height:"11",x:"3",y:"11",rx:"2",ry:"2"}],["path",{d:"M7 11V7a5 5 0 0 1 10 0v4"}]]),R0=b("log-out",[["path",{d:"m16 17 5-5-5-5"}],["path",{d:"M21 12H9"}],["path",{d:"M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"}]]);b("medal",[["path",{d:"M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"}],["path",{d:"M11 12 5.12 2.2"}],["path",{d:"m13 12 5.88-9.8"}],["path",{d:"M8 7h8"}],["circle",{cx:"12",cy:"17",r:"5"}],["path",{d:"M12 18v-2h-.5"}]]);const P0=b("megaphone",[["path",{d:"M11 6a13 13 0 0 0 8.4-2.8A1 1 0 0 1 21 4v12a1 1 0 0 1-1.6.8A13 13 0 0 0 11 14H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z"}],["path",{d:"M6 14a12 12 0 0 0 2.4 7.2 2 2 0 0 0 3.2-2.4A8 8 0 0 1 10 14"}],["path",{d:"M8 6v8"}]]),j0=b("menu",[["path",{d:"M4 5h16"}],["path",{d:"M4 12h16"}],["path",{d:"M4 19h16"}]]);b("monitor-play",[["path",{d:"M15.033 9.44a.647.647 0 0 1 0 1.12l-4.065 2.352a.645.645 0 0 1-.968-.56V7.648a.645.645 0 0 1 .967-.56z"}],["path",{d:"M12 17v4"}],["path",{d:"M8 21h8"}],["rect",{x:"2",y:"3",width:"20",height:"14",rx:"2"}]]);b("package",[["path",{d:"M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"}],["path",{d:"M12 22V12"}],["polyline",{points:"3.29 7 12 12 20.71 7"}],["path",{d:"m7.5 4.27 9 5.15"}]]);b("chart-pie",[["path",{d:"M21 12c.552 0 1.005-.449.95-.998a10 10 0 0 0-8.953-8.951c-.55-.055-.998.398-.998.95v8a1 1 0 0 0 1 1z"}],["path",{d:"M21.21 15.89A10 10 0 1 1 8 2.83"}]]);b("plug",[["path",{d:"M12 22v-5"}],["path",{d:"M15 8V2"}],["path",{d:"M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z"}],["path",{d:"M9 8V2"}]]);b("plus",[["path",{d:"M5 12h14"}],["path",{d:"M12 5v14"}]]);b("power",[["path",{d:"M12 2v10"}],["path",{d:"M18.4 6.6a9 9 0 1 1-12.77.04"}]]);b("power-off",[["path",{d:"M18.36 6.64A9 9 0 0 1 20.77 15"}],["path",{d:"M6.16 6.16a9 9 0 1 0 12.68 12.68"}],["path",{d:"M12 2v4"}],["path",{d:"m2 2 20 20"}]]);const $0=b("presentation",[["path",{d:"M2 3h20"}],["path",{d:"M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"}],["path",{d:"m7 21 5-5 5 5"}]]);b("refresh-cw",[["path",{d:"M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"}],["path",{d:"M21 3v5h-5"}],["path",{d:"M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"}],["path",{d:"M8 16H3v5"}]]);b("rotate-ccw",[["path",{d:"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"}],["path",{d:"M3 3v5h5"}]]);b("save",[["path",{d:"M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"}],["path",{d:"M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"}],["path",{d:"M7 3v4a1 1 0 0 0 1 1h7"}]]);const F0=b("scale",[["path",{d:"M12 3v18"}],["path",{d:"m19 8 3 8a5 5 0 0 1-6 0zV7"}],["path",{d:"M3 7h1a17 17 0 0 0 8-2 17 17 0 0 0 8 2h1"}],["path",{d:"m5 8 3 8a5 5 0 0 1-6 0zV7"}],["path",{d:"M7 21h10"}]]);b("scroll-text",[["path",{d:"M15 12h-5"}],["path",{d:"M15 8h-5"}],["path",{d:"M19 17V5a2 2 0 0 0-2-2H4"}],["path",{d:"M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"}]]);const s0=b("search",[["path",{d:"m21 21-4.34-4.34"}],["circle",{cx:"11",cy:"11",r:"8"}]]);b("shield",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}]]);b("shield-alert",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["path",{d:"M12 8v4"}],["path",{d:"M12 16h.01"}]]);b("shield-check",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"}],["path",{d:"m9 12 2 2 4-4"}]]);b("shopping-bag",[["path",{d:"M16 10a4 4 0 0 1-8 0"}],["path",{d:"M3.103 6.034h17.794"}],["path",{d:"M3.4 5.467a2 2 0 0 0-.4 1.2V20a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6.667a2 2 0 0 0-.4-1.2l-2-2.667A2 2 0 0 0 17 2H7a2 2 0 0 0-1.6.8z"}]]);b("siren",[["path",{d:"M7 18v-6a5 5 0 1 1 10 0v6"}],["path",{d:"M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z"}],["path",{d:"M21 12h1"}],["path",{d:"M18.5 4.5 18 5"}],["path",{d:"M2 12h1"}],["path",{d:"M12 2v1"}],["path",{d:"m4.929 4.929.707.707"}],["path",{d:"M12 12v6"}]]);b("timer",[["line",{x1:"10",x2:"14",y1:"2",y2:"2"}],["line",{x1:"12",x2:"15",y1:"14",y2:"11"}],["circle",{cx:"12",cy:"14",r:"8"}]]);b("trending-up",[["path",{d:"M16 7h6v6"}],["path",{d:"m22 7-8.5 8.5-5-5L2 17"}]]);const z0=b("trophy",[["path",{d:"M10 14.66V17a1 1 0 0 1-1 1 2 2 0 0 0-2 2v2"}],["path",{d:"M14 14.66V17a1 1 0 0 0 1 1 2 2 0 0 1 2 2v2"}],["path",{d:"M17.916 10H19.5A2.5 2.5 0 0 0 22 7.5V5a1 1 0 0 0-1-1h-3"}],["path",{d:"M4 22h16"}],["path",{d:"M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z"}],["path",{d:"M6.084 10H4.5A2.5 2.5 0 0 1 2 7.5V5a1 1 0 0 1 1-1h3"}]]),B0=b("user",[["path",{d:"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"}],["circle",{cx:"12",cy:"7",r:"4"}]]);b("user-check",[["path",{d:"m16 11 2 2 4-4"}],["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}]]);b("user-cog",[["path",{d:"M10 15H6a4 4 0 0 0-4 4v2"}],["path",{d:"m14.305 16.53.923-.382"}],["path",{d:"m15.228 13.852-.923-.383"}],["path",{d:"m16.852 12.228-.383-.923"}],["path",{d:"m16.852 17.772-.383.924"}],["path",{d:"m19.148 12.228.383-.923"}],["path",{d:"m19.53 18.696-.382-.924"}],["path",{d:"m20.772 13.852.924-.383"}],["path",{d:"m20.772 16.148.924.383"}],["circle",{cx:"18",cy:"15",r:"3"}],["circle",{cx:"9",cy:"7",r:"4"}]]);b("user-plus",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}],["line",{x1:"19",x2:"19",y1:"8",y2:"14"}],["line",{x1:"22",x2:"16",y1:"11",y2:"11"}]]);b("user-x",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["circle",{cx:"9",cy:"7",r:"4"}],["line",{x1:"17",x2:"22",y1:"8",y2:"13"}],["line",{x1:"22",x2:"17",y1:"8",y2:"13"}]]);b("users",[["path",{d:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"}],["path",{d:"M16 3.128a4 4 0 0 1 0 7.744"}],["path",{d:"M22 21v-2a4 4 0 0 0-3-3.87"}],["circle",{cx:"9",cy:"7",r:"4"}]]);b("users-round",[["path",{d:"M18 21a8 8 0 0 0-16 0"}],["circle",{cx:"10",cy:"8",r:"5"}],["path",{d:"M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3"}]]);b("video",[["path",{d:"m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"}],["rect",{x:"2",y:"6",width:"14",height:"12",rx:"2"}]]);const H0=b("wallet",[["path",{d:"M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"}],["path",{d:"M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"}]]);b("wrench",[["path",{d:"M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.106-3.105c.32-.322.863-.22.983.218a6 6 0 0 1-8.259 7.057l-7.91 7.91a1 1 0 0 1-2.999-3l7.91-7.91a6 6 0 0 1 7.057-8.259c.438.12.54.662.219.984z"}]]);const V0=b("x",[["path",{d:"M18 6 6 18"}],["path",{d:"m6 6 12 12"}]]);b("circle-x",[["circle",{cx:"12",cy:"12",r:"10"}],["path",{d:"m15 9-6 6"}],["path",{d:"m9 9 6 6"}]]);b("camera",[["path",{d:"M13.997 4a2 2 0 0 1 1.76 1.05l.486.9A2 2 0 0 0 18.003 7H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1.997a2 2 0 0 0 1.759-1.048l.489-.904A2 2 0 0 1 10.004 4z"}],["circle",{cx:"12",cy:"13",r:"3"}]]);b("upload",[["path",{d:"M12 3v12"}],["path",{d:"m17 8-5-5-5 5"}],["path",{d:"M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"}]]);b("trash",[["path",{d:"M10 11v6"}],["path",{d:"M14 11v6"}],["path",{d:"M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"}],["path",{d:"M3 6h18"}],["path",{d:"M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"}]]);b("pencil",[["path",{d:"M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"}],["path",{d:"m15 5 4 4"}]]);b("mail",[["path",{d:"m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7"}],["rect",{x:"2",y:"4",width:"20",height:"16",rx:"2"}]]);b("phone",[["path",{d:"M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384"}]]);b("map-pin",[["path",{d:"M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"}],["circle",{cx:"12",cy:"10",r:"3"}]]);b("smartphone",[["rect",{width:"14",height:"20",x:"5",y:"2",rx:"2",ry:"2"}],["path",{d:"M12 18h.01"}]]);b("languages",[["path",{d:"m5 8 6 6"}],["path",{d:"m4 14 6-6 2-3"}],["path",{d:"M2 5h12"}],["path",{d:"M7 2h1"}],["path",{d:"m22 22-5-10-5 10"}],["path",{d:"M14 18h6"}]]);b("palette",[["path",{d:"M12 22a1 1 0 0 1 0-20 10 9 0 0 1 10 9 5 5 0 0 1-5 5h-2.25a1.75 1.75 0 0 0-1.4 2.8l.3.4a1.75 1.75 0 0 1-1.4 2.8z"}],["circle",{cx:"13.5",cy:"6.5",r:".5",fill:"currentColor"}],["circle",{cx:"17.5",cy:"10.5",r:".5",fill:"currentColor"}],["circle",{cx:"6.5",cy:"12.5",r:".5",fill:"currentColor"}],["circle",{cx:"8.5",cy:"7.5",r:".5",fill:"currentColor"}]]);b("image",[["rect",{width:"18",height:"18",x:"3",y:"3",rx:"2",ry:"2"}],["circle",{cx:"9",cy:"9",r:"2"}],["path",{d:"m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"}]]);const U0=Kt.forwardRef(function({lift:t=!0,className:n="",children:i,...r},s){return W.jsx("section",{ref:s,className:["eos-panel",t?"eos-lift":"",n].filter(Boolean).join(" "),...r,children:i})});function K0({title:e,subtitle:t,action:n,icon:i,as:r="h2",id:s}){return W.jsxs("div",{className:"eos-panel__header",children:[W.jsxs("div",{style:{minWidth:0},children:[W.jsxs(r,{className:"eos-panel__title",id:s,children:[i&&W.jsx("span",{className:"eos-chip","aria-hidden":!0,children:i}),e]}),t&&W.jsx("p",{className:"eos-panel__subtitle",children:t})]}),n]})}function W0({flush:e=!1,children:t,style:n}){return W.jsx("div",{className:e?"eos-panel__body eos-panel__body--flush":"eos-panel__body",style:n,children:t})}function q0({title:e,children:t,icon:n,action:i}){return W.jsxs("div",{className:"eos-empty",children:[W.jsx("span",{className:"eos-empty__icon","aria-hidden":!0,children:n??W.jsx(s0,{})}),e&&W.jsx("span",{className:"eos-empty__title",children:e}),t&&W.jsx("span",{children:t}),i]})}function Q0({title:e="Could not load",children:t,onRetry:n}){return W.jsxs("div",{className:"eos-empty eos-empty--error",role:"alert",children:[W.jsx("span",{className:"eos-empty__icon","aria-hidden":!0,children:W.jsx(r0,{})}),W.jsx("span",{className:"eos-empty__title",children:e}),t&&W.jsx("span",{children:t}),n&&W.jsx("button",{type:"button",className:"eos-btn eos-btn--secondary eos-btn--sm",onClick:n,children:"Try again"})]})}function o0({width:e="100%",height:t=14,radius:n,style:i}){return W.jsx("span",{className:"eos-skeleton","aria-hidden":!0,style:{width:e,height:t,borderRadius:n,...i}})}function G0({lines:e=3}){return W.jsx("div",{"aria-busy":"true","aria-label":"Loading",style:{display:"flex",flexDirection:"column",gap:10},children:Array.from({length:e},(t,n)=>W.jsx(o0,{width:`${100-n%3*18}%`},n))})}function Y0({tone:e="neutral",dot:t=!1,children:n}){return W.jsx("span",{className:["eos-badge",e==="neutral"?"":`eos-badge--${e}`,t?"eos-badge--dot":""].filter(Boolean).join(" "),children:n})}export{P0 as $,wm as A,S0 as B,A0 as C,$0 as D,Q0 as E,E0 as F,N0 as G,T0 as H,I0 as I,F0 as J,D0 as K,x0 as L,j0 as M,L0 as N,q0 as O,n0 as P,Y0 as Q,a0 as R,G0 as S,z0 as T,B0 as U,_0 as V,H0 as W,V0 as X,d0 as Y,ym as Z,k0 as _,l0 as a,f0 as b,u0 as c,m0 as d,g0 as e,p0 as f,vm as g,y0 as h,w0 as i,W as j,h0 as k,c0 as l,yi as m,Ml as n,U0 as o,_l as p,K0 as q,Kt as r,W0 as s,M0 as t,O0 as u,C0 as v,s0 as w,R0 as x,v0 as y,b0 as z};
