'use strict';
// Translate only developer-authored text. Never pass documents or quotations to markup().
const i18n=(()=>{
 const key='legal-library-language';
 let language='vi';
 try{if(localStorage.getItem(key)==='en')language='en';}catch{}
 const dictionary=window.LEGAL_LIBRARY_VI;
 function t(value){if(language==='en'||typeof value!=='string')return value;const core=value.trim();return dictionary[value]??(dictionary[core]?value.replace(core,dictionary[core]):value);}
 function spaced(value){const core=value.trim();return core&&Object.hasOwn(dictionary,core)?value.replace(core,t(core)):value;}
 function markup(source){
  if(language==='en')return source;
  // Interpolated values are placeholders at this point, so source data is untouched.
  return source.replace(/(^|>)([^<]*)(?=<|$)/g,(_,prefix,text)=>prefix+spaced(text))
   .replace(/\b(placeholder|aria-label|title)="([^"]*)"/g,(_,name,text)=>`${name}="${spaced(text)}"`);
 }
 function html(strings,...values){
  const source=strings.map((part,index)=>part+(index<values.length?'{{'+index+'}}':'')).join('');
  return markup(source).replace(/\{\{(\d+)\}\}/g,(_,index)=>String(values[Number(index)]??''));
 }
 function message(value){
  if(typeof value!=='string'||language==='en')return value;
  if(Object.hasOwn(dictionary,value))return t(value);
  // Known operational messages may carry a page number or a technical detail.
  const page=value.match(/^Page (\d+): (.*)$/s);
  if(page)return `Trang ${page[1]}: ${message(page[2])}`;
  const provenance='Vision OCR produced this transcription. It may omit or invent words, numbers or table structure. No calibrated recognition confidence is available. Compare all relied-on passages with the original scan.';
  return value.replace(provenance,'Văn bản này được nhận dạng bằng OCR thị giác. Kết quả có thể bỏ sót hoặc tạo thêm từ ngữ, số liệu hoặc cấu trúc bảng. Không có mức độ tin cậy nhận dạng đã được hiệu chuẩn. Hãy đối chiếu mọi đoạn được sử dụng với bản quét gốc.')
   .replace('Vision-transcribed page numbers:','Các trang được nhận dạng bằng mô hình thị giác:')
   .replace('Scanned text was recognized automatically. Verify figures, dates and tables against the original.',t('Scanned text was recognized automatically. Verify figures, dates and tables against the original.'));
 }
 function display(value){
  const labels={admin:'Administrator',member:'Team member',active:'Active',pending:'Pending approval',disabled:'Disabled',
   ACTIVE:'Active',ARCHIVED:'Archived',OWNER:'Owner',VIEWER:'Viewer',CONTRIBUTOR:'Contributor',MANAGER:'Manager',
   useful:'Useful',wrong_source:'Wrong source',outdated:'Outdated information',incomplete:'Incomplete',unsupported:'Does not support the question',
   hybrid:'Hybrid',lexical:'Keyword',semantic:'Semantic',unknown:'Unknown'};
  return t(labels[value]||value);
 }
 function initialize(){
  document.documentElement.lang=language;
  document.title=t('Legal Library');
  document.querySelector('.skip').textContent=t('Skip to content');
  document.querySelector('#root [role=status]').textContent=t('Opening your library…');
  const control=document.getElementById('language-select');control.value=language;
 }
 function change(next){
  if(!['vi','en'].includes(next))return false;
  try{localStorage.setItem(key,next);return true;}catch{return false;}
 }
 return {t,markup,html,message,display,initialize,change,language,locale:language==='vi'?'vi-VN':'en-US'};
})();
i18n.initialize();
