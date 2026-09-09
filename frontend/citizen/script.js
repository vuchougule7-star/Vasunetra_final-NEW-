/* =========================================
   VASUNETRA CITIZEN DASHBOARD
   Live backend + safe fallback prototype data
========================================= */

const fallbackRows = {
  Sialsuk:{name:"Sialsuk",risk:"HIGH",riskValue:78,rainfall:"Heavy",terrain:"Steep",landChange:"14.6% detected",description:"Higher risk indicators are shown. Stay alert and follow official safety instructions.",safeZone:"Sialsuk Community Relief Centre",distance:"Approximately 2.4 km away",latitude:23.72,longitude:92.65,safeLat:23.725,safeLon:92.658},
  Zohmun:{name:"Zohmun",risk:"HIGH",riskValue:61,rainfall:"Heavy",terrain:"Hilly",landChange:"No recent change",description:"Higher risk indicators are shown. Stay alert and follow official safety instructions.",safeZone:"Zohmun Emergency Shelter",distance:"Approximately 1.9 km away",latitude:23.78,longitude:92.63,safeLat:23.785,safeLon:92.637},
  Thenzawl:{name:"Thenzawl",risk:"MEDIUM",riskValue:50,rainfall:"Heavy",terrain:"Hilly",landChange:"No recent change",description:"Moderate risk conditions detected. Residents should stay alert and monitor official updates.",safeZone:"Thenzawl Community Safety Centre",distance:"Approximately 2.1 km away",latitude:23.32,longitude:92.73,safeLat:23.325,safeLon:92.735},
  Reiek:{name:"Reiek",risk:"LOW",riskValue:25,rainfall:"Light",terrain:"Moderate",landChange:"No major change",description:"Current indicators show relatively low risk. Continue monitoring official updates.",safeZone:"Reiek Community Shelter",distance:"Approximately 3.0 km away",latitude:23.76,longitude:92.57,safeLat:23.765,safeLon:92.575},
  Aizawl_Rural1:{name:"Aizawl Rural 1",risk:"HIGH",riskValue:65,rainfall:"Moderate",terrain:"Steep",landChange:"No recent change",description:"Higher risk indicators are shown. Stay alert and follow official safety instructions.",safeZone:"Aizawl Rural Relief Centre",distance:"Approximately 1.6 km away",latitude:23.74,longitude:92.72,safeLat:23.748,safeLon:92.728},
  Aizawl_Rural2:{name:"Aizawl Rural 2",risk:"MEDIUM",riskValue:42,rainfall:"Moderate",terrain:"Hilly",landChange:"No recent change",description:"Moderate risk conditions detected. Residents should stay alert and monitor official updates.",safeZone:"Aizawl Rural Safety Centre",distance:"Approximately 2.7 km away",latitude:23.78,longitude:92.70,safeLat:23.786,safeLon:92.706},
  Lungdai:{name:"Lungdai",risk:"HIGH",riskValue:63,rainfall:"Heavy",terrain:"Steep",landChange:"No recent change",description:"Higher risk indicators are shown. Stay alert and follow official safety instructions.",safeZone:"Lungdai Emergency Shelter",distance:"Approximately 2.2 km away",latitude:23.55,longitude:92.67,safeLat:23.556,safeLon:92.676}
};
let villageData={...fallbackRows};
let map,userMarker,safeMarker,routeLine;
let currentVillage=Object.keys(villageData)[0];

function toggleMenu(){
  const menu=document.getElementById("mobileMenu");
  menu.style.display=menu.style.display==="block"?"none":"block";
}

function riskFromScore(score){
  if(score>.55)return "HIGH";
  if(score>.35)return "MEDIUM";
  return "LOW";
}

function riskValue(score){ return Math.max(0,Math.min(100,Math.round(score*100))); }

async function loadLiveData(){
  try{
    const r=await fetch("/api/villages",{cache:"no-store"});
    if(!r.ok) throw new Error();
    const rows=await r.json();
    if(!rows.length) throw new Error();
    villageData={};
    rows.forEach(d=>{
      const key=String(d.village);
      villageData[key]={
        name:key.replaceAll("_"," "),
        risk:riskFromScore(Number(d.hazard_score||0)),
        riskValue:riskValue(Number(d.hazard_score||0)),
        rainfall:Number(d.rainfall||0)>.65?"Heavy":Number(d.rainfall||0)>.4?"Moderate":"Light",
        terrain:Number(d.slope||0)>.65?"Steep":Number(d.slope||0)>.4?"Hilly":"Moderate",
        landChange:Number(d.land_change||0)>0?`${(Number(d.land_change)*100).toFixed(1)}% detected`:"No major change",
        description:`${d.recommended_action}. Residents should follow authorised disaster-management instructions.`,
        safeZone:d.safe_zone||"Designated Community Safe Zone",
        distance:`Approximately ${Number(d.safe_zone_distance_km||2.5).toFixed(1)} km away`,
        latitude:Number(d.latitude||23.73),longitude:Number(d.longitude||92.68),
        safeLat:Number(d.safe_zone_lat||d.latitude||23.73),safeLon:Number(d.safe_zone_lon||d.longitude||92.68)
      };
    });
    currentVillage=Object.keys(villageData)[0];
    populateVillages();
    changeVillage();
  }catch(e){
    populateVillages();
    changeVillage();
  }
}

function populateVillages(){
  const select=document.getElementById("villageSelect");
  const old=currentVillage;
  select.innerHTML=Object.keys(villageData).map(k=>`<option value="${k}">${villageData[k].name}</option>`).join("");
  if(villageData[old])select.value=old;
}

function changeVillage(){
  const selected=document.getElementById("villageSelect").value;
  currentVillage=selected;
  const data=villageData[selected];
  if(!data)return;

  document.getElementById("riskTitle").textContent=data.risk;
  document.getElementById("riskDescription").textContent=data.description;
  document.getElementById("rainfall").textContent=data.rainfall;
  document.getElementById("terrain").textContent=data.terrain;
  document.getElementById("landChange").textContent=data.landChange;
  document.getElementById("meterFill").style.width=data.riskValue+"%";

  const card=document.getElementById("riskCard"), title=document.getElementById("riskTitle"), icon=document.getElementById("riskIcon");
  if(data.risk==="HIGH"){
    card.style.borderLeft="6px solid #d9534f";title.style.color="#d9534f";icon.textContent="🚨";document.getElementById("meterFill").style.background="#d9534f";
  }else if(data.risk==="LOW"){
    card.style.borderLeft="6px solid #0c7c59";title.style.color="#0c7c59";icon.textContent="✅";document.getElementById("meterFill").style.background="#0c7c59";
  }else{
    card.style.borderLeft="6px solid #e0a000";title.style.color="#d18d00";icon.textContent="⚠️";document.getElementById("meterFill").style.background="#e0a000";
  }

  document.getElementById("safeZoneName").textContent=data.safeZone;
  document.getElementById("safeZoneDistance").textContent=data.distance;
  document.getElementById("alertText").textContent =
    data.risk==="HIGH" ? "Higher risk indicators are currently shown for this area. Stay alert and follow official instructions." :
    data.risk==="LOW" ? "No major warning is shown in the current prototype indicators. Continue monitoring official updates." :
    "Moderate conditions are currently shown. Stay alert during heavy rainfall and monitor official updates.";

  if(map){
    map.setView([data.latitude,data.longitude],13);
    userMarker.setLatLng([data.latitude,data.longitude]).bindPopup(`<b>Your Selected Area</b><br>${data.name}`);
    safeMarker.setLatLng([data.safeLat,data.safeLon]).bindPopup(`<b>🛟 ${data.safeZone}</b><br>Safe Zone`);
    if(routeLine)routeLine.setLatLngs([[data.latitude,data.longitude],[data.safeLat,data.safeLon]]);
  }
}

function findSafeZone(){
  const result=document.getElementById("safeZoneResult");
  result.classList.remove("hidden");
  result.scrollIntoView({behavior:"smooth",block:"center"});
}

function showRoute(){
  const d=villageData[currentVillage];
  if(map){
    map.fitBounds([[d.latitude,d.longitude],[d.safeLat,d.safeLon]],{padding:[40,40]});
    if(routeLine)routeLine.openPopup();
  }
  alert(`Safe-zone route\n\n${d.safeZone}\n${d.distance}\n\nThis prototype shows a direct map connection. Follow authorised local evacuation instructions and use designated routes.`);
}

async function reportIssue(){
  const issue=prompt("What issue would you like to report?\n\nExample: Waterlogging, road blockage, slope damage");
  if(!issue||!issue.trim())return;
  try{
    const r=await fetch("/api/citizen/report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({village:currentVillage,issue:issue.trim()})});
    if(!r.ok)throw new Error();
    const x=await r.json();
    alert(`Thank you.\n\nYour report has been received.\nReference: ${x.id}\nStatus: ${x.status}`);
  }catch(e){
    alert("Thank you.\n\nYour report has been recorded in this prototype.");
  }
}

function showAlertDetails(){
  const d=villageData[currentVillage];
  alert(`IMPORTANT SAFETY INFORMATION\n\n• Current risk: ${d.risk}\n• Land-change indicator: ${d.landChange}\n• Avoid unnecessary travel near vulnerable slopes.\n• Follow instructions from authorised disaster-management authorities.\n\nThis dashboard is a prototype information and decision-support interface.`);
}

function showEmergency(){
  alert("EMERGENCY GUIDANCE\n\nMove toward a designated safe zone when instructed by authorised authorities.\n\nThis prototype does not replace official emergency services or government instructions.");
}

function initMap(){
  map=L.map("map").setView([23.73,92.68],10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:"&copy; OpenStreetMap contributors"}).addTo(map);
  const d=villageData[currentVillage];
  userMarker=L.marker([d.latitude,d.longitude]).addTo(map).bindPopup(`<b>Your Selected Area</b><br>${d.name}`);
  safeMarker=L.marker([d.safeLat,d.safeLon]).addTo(map).bindPopup(`<b>🛟 ${d.safeZone}</b><br>Safe Zone`);
  routeLine=L.polyline([[d.latitude,d.longitude],[d.safeLat,d.safeLon]]).addTo(map).bindPopup("Prototype route to designated safe zone");
}

document.addEventListener("DOMContentLoaded",()=>{
  initMap();
  loadLiveData();
  document.getElementById("lastUpdated").textContent=new Date().toLocaleDateString(undefined,{day:"2-digit",month:"short",year:"numeric"});
});
