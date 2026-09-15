"""Independent 12-row synthetic submission; no C fixture imports."""
import json
from pathlib import Path

ROWS=[("r1","X","4.2","sampling",0,"d1s","t1"),("r2","Y","7","sampling",0,"d1s","t1"),("r3","X","4.2","sampling",3,"d2s","t2"),("r4","X","4.2","sampling",0,"d3s","t3"),("r5","X","5.1","sampling",None,None,"t4"),("r6","X","6","sampling",None,None,"t5"),("r7","X","8","sampling",0,"d6","t6"),("r8","X","9","sampling",2,"d7","t7"),("r9","X","1","sampling",None,None,"t8"),("r10","X","2","sampling",None,None,"t9"),("r11","X","4.2","sampling",0,"d10","t10"),("r12","X","3","sampling",None,None,"t12")]

def build_submission():
    observations=[]
    for rid,item,value,role,day,date_ref,scope in ROWS:
        special={"r5":("report",2,"C1","d4r","lr-t4","t4"),"r6":("document",2,"C1","d5","ld-t5","t5"),"r7":("sampling",0,"C2","d6","ls-t6","t6"),"r8":("sampling",2,"C1","d7","ls-t7","t7"),"r11":("sampling",0,"C1","d10","ls-t10","t10")}
        coord = "C1"; role_ref = "ls-" + scope
        if rid in special: role,day,coord,date_ref,role_ref,scope=special[rid]
        a={"role":role,"relative_day":day,"coordinate_id":coord if day is not None else None,"date_ref":date_ref,"role_ref":role_ref if day is not None else None,"scope_ref":scope if day is not None else None,"binding_status":"explicit" if day is not None else "unknown"}
        if rid in {"r1","r2","r3","r4"}:
            a2={"role":"report","relative_day":(day+1),"coordinate_id":"C1","date_ref":{"r1":"d1r","r2":"d1r","r3":"d2r","r4":"d3r"}[rid],"role_ref":"lr-"+scope,"scope_ref":scope,"binding_status":"explicit"}
            assertions=[a,a2]
        elif rid == "r9":
            assertions=[{"role":"sampling","relative_day":0,"coordinate_id":"C1","date_ref":"d8a","role_ref":"ls-t8","scope_ref":"t8","binding_status":"conflicting"},{"role":"sampling","relative_day":1,"coordinate_id":"C1","date_ref":"d8b","role_ref":"ls-t8","scope_ref":"t8","binding_status":"conflicting"}]
        elif rid == "r10":
            assertions=[{"role":"sampling","relative_day":None,"coordinate_id":None,"date_ref":None,"role_ref":None,"scope_ref":None,"binding_status":"unresolved"},{"role":"unknown","relative_day":0,"coordinate_id":"C1","date_ref":"d9","role_ref":None,"scope_ref":None,"binding_status":"unresolved"}]
        elif rid == "r12":
            assertions=[{"role":"sampling","relative_day":None,"coordinate_id":None,"date_ref":None,"role_ref":None,"scope_ref":None,"binding_status":"unresolved"}]
        else:
            assertions=[a]
            if role != "sampling":
                assertions.insert(0,{"role":"sampling","relative_day":None,"coordinate_id":None,"date_ref":None,"role_ref":None,"scope_ref":None,"binding_status":"unknown"})
        note = (f"Synthetic row {rid}: value {value} U; explicit sampling day {day} "
                f"from date evidence {date_ref} within scope {scope}." if day is not None
                else f"Synthetic row {rid}: value {value} U; sampling date is not stated or is unresolved in source scope {scope}.")
        observations.append({"observation_id":"obs-"+rid,"case_token":"SYNTHETIC-ONLY","item":item,"value":value,"unit":"U","time_assertions":assertions,"source_refs":[rid],"evidence_note":note})
    return {"protocol":"research-card-v0.3/shared-synthetic-v0.1","observations":observations,"event_groups":[["r1","r4"],["r3"],["r11"]],"cost":{"attempts":[],"wall_seconds":0,"currency":"USD"}}

if __name__ == "__main__":
    out=Path(__file__).with_name("independent_source_submission.json")
    out.write_text(json.dumps(build_submission(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(out)
