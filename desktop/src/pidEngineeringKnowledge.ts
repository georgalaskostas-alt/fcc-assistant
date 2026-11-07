/** Starter engineering hints. These are NOT reproductions of ISA/ISO standards or site-approved legends. */
export type PidKnowledgeMatch={id:string;category:"instrument"|"line"|"equipment"|"note"|"valve";label:string;reason:string;reference:string;confidence:"pattern_only"};
type Rule={id:string;category:PidKnowledgeMatch["category"];label:string;pattern:RegExp;reason:string;reference:string};
const rules:Rule[]=[
 {id:"instrument-pressure",category:"instrument",label:"Pressure instrument",pattern:/^(?:PI|PT|PIC|PIT|PSH|PSL)\s*[- ]?\d{2,5}[A-Z]?$/i,reason:"Instrument-letter prefix resembles a pressure function; verify symbol and tag on the drawing.",reference:"ISA-5.1 family — consult licensed edition and site legend"},
 {id:"instrument-flow",category:"instrument",label:"Flow instrument",pattern:/^(?:FI|FT|FIC|FIT|FV|FCV)\s*[- ]?\d{2,5}[A-Z]?$/i,reason:"Instrument-letter prefix resembles a flow function; confirm actual instrument designation.",reference:"ISA-5.1 family — consult licensed edition and site legend"},
 {id:"instrument-level",category:"instrument",label:"Level instrument",pattern:/^(?:LI|LT|LIC|LG|LSH|LSL|LAH|LAL)\s*[- ]?\d{2,5}[A-Z]?$/i,reason:"Instrument-letter prefix resembles a level function.",reference:"ISA-5.1 family — consult licensed edition and site legend"},
 {id:"instrument-temperature",category:"instrument",label:"Temperature instrument",pattern:/^(?:TI|TT|TIC|TE)\s*[- ]?\d{2,5}[A-Z]?$/i,reason:"Instrument-letter prefix resembles a temperature function.",reference:"ISA-5.1 family — consult licensed edition and site legend"},
 {id:"line-number",category:"line",label:"Candidate line identifier",pattern:/^\d{1,2}["”]?[-–][A-Z0-9]{1,4}[-–]\d{4,7}(?:[-–][A-Z0-9]+)?$/i,reason:"Looks like a pipe size followed by service/sequence/class; each field is site-specific.",reference:"Site piping numbering specification required"},
 {id:"drawing-note",category:"note",label:"Drawing note reference",pattern:/^\(?NOTE\s*\d{1,3}\)?$/i,reason:"Explicit drawing-note reference, not equipment.",reference:"Drawing notes and project legend"},
 {id:"equipment-m",category:"equipment",label:"Possible equipment tag",pattern:/^M[-–]\d{3,6}[A-Z]?$/i,reason:"Matches the observed M-4252-style site tag; M must not be interpreted without the equipment list.",reference:"Site equipment register / drawing legend required"},
 {id:"valve-prv",category:"valve",label:"PRV-tagged valve candidate",pattern:/^PRV[-–]?\d{2,5}[A-Z]?$/i,reason:"PRV abbreviation is context-dependent; do not infer relief or pressure-regulating function from text alone.",reference:"Site valve legend, datasheet and P&ID required"},
];
export function matchPidKnowledge(tag:string):PidKnowledgeMatch[]{
 const normalized=tag.normalize("NFKC").replace(/[‐‑‒–—−]/g,"-").replace(/[\u200B-\u200D\uFEFF]/g,"").replace(/\s+/g," ").trim();
 return rules.filter(rule=>rule.pattern.test(normalized)).map(({id,category,label,reason,reference})=>({id,category,label,reason,reference,confidence:"pattern_only" as const}));
}
export const pidKnowledgeReferences=[
 {name:"ANSI/ISA-5.1",scope:"Instrumentation symbols and identification",note:"External standard; no normative diagrams or proprietary text embedded."},
 {name:"ISO 10628",scope:"Diagrams for chemical and petrochemical industry",note:"External standard; consult the applicable edition."},
 {name:"ISO 14617",scope:"Graphical symbols for diagrams",note:"External standard; consult the applicable edition."},
 {name:"Site legend / equipment register",scope:"Plant-specific tag numbering and symbols",note:"Not yet provided or validated."},
];
