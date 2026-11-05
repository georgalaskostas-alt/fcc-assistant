import type { PidOcrResult } from "./api";

type Candidate=PidOcrResult["candidates"][number];
export type CandidateAssessment={tier:"plausible"|"uncertain";reasons:string[];score:number};

/** Heuristic triage, not recognition or engineer verification. Never discard detections. */
export function assessPidCandidate(candidate:Candidate):CandidateAssessment{
  const tag=candidate.tag.trim().toUpperCase();
  const reasons:string[]=[];
  let score=0;
  if(candidate.confidence>=75){score+=2;reasons.push("Higher OCR confidence");}
  else if(candidate.confidence>=50){score+=1;reasons.push("Moderate OCR confidence");}
  else reasons.push("Low OCR confidence");
  const patterns=[
    /^(?:[A-Z]{1,5})[- ]?\d{2,5}[A-Z]?$/,
    /^\d{1,2}["”]?-?[A-Z0-9]{1,5}-\d{3,7}(?:-[A-Z0-9]+)?$/,
    /^(?:NOTE)\s*\d{1,3}$/,
  ];
  if(patterns.some(pattern=>pattern.test(tag))){score+=2;reasons.push("Resembles a technical label");}
  else if(/^[A-Z0-9"\/-]{3,32}$/.test(tag)){score+=1;reasons.push("Possible label; format unconfirmed");}
  else reasons.push("Fragment or unsupported label format");
  if(/^[A-Z]{0,2}\d?$/.test(tag)){score-=2;reasons.push("Very short fragment");}
  const b=candidate.box;
  if(b.width<=0||b.height<=0||b.width>0.5||b.height>0.1){score-=2;reasons.push("Unusual bounding box");}
  return {tier:score>=3?"plausible":"uncertain",reasons,score};
}
