import argparse
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Any

# Add the parent directory to sys.path to import fit_utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fit_utils import read_fit_file

def print_separator(title: str = ""):
    if title:
        print(f"\n--- {title} ---")
    else:
        print("-" * 40)

def format_val(val: Any) -> str:
    if isinstance(val, (int, float)) and val > 1000000000: # Likely a timestamp
        try:
            return f"{val} ({datetime.fromtimestamp(val/1000)})"
        except:
            return str(val)
    return str(val)

def get_messages_by_type(fit_file: Any, type_names: list[str]) -> list[Any]:
    return [r.message for r in fit_file.records if type(r.message).__name__ in type_names]

def do_summary(fit_path: str):
    print(f"Summary for: {fit_path}")
    fit_file = read_fit_file(fit_path)
    msg_types = [type(r.message).__name__ for r in fit_file.records]
    counts = Counter(msg_types)
    
    print_separator("Message Counts")
    for mtype, count in sorted(counts.items()):
        print(f"{mtype:25}: {count}")
    
    # Extract some high-level info if available
    sessions = get_messages_by_type(fit_file, ["SessionMessage"])
    if sessions:
        s = sessions[0]
        print_separator("Session Info")
        print(f"Sport      : {getattr(s, 'sport', 'N/A')}")
        print(f"Sub Sport  : {getattr(s, 'sub_sport', 'N/A')}")
        print(f"Start Time : {format_val(getattr(s, 'start_time', 'N/A'))}")
        print(f"Duration   : {getattr(s, 'total_elapsed_time', 'N/A')}s")
        print(f"Distance   : {getattr(s, 'total_distance', 'N/A')}m")

def do_inspect(fit_path: str, message_types: list[str], limit: int = 0):
    fit_file = read_fit_file(fit_path)
    
    counts = Counter()
    for record in fit_file.records:
        msg = record.message
        m_type = type(msg).__name__
        
        if not message_types or m_type in message_types:
            if limit > 0 and counts[m_type] >= limit:
                continue
            
            counts[m_type] += 1
            print(f"\n[{m_type}]")
            for field in msg.fields:
                val = field.get_value()
                if val is not None:
                    print(f"  {field.name:25}: {val}")

def do_consistency(fit_path: str):
    fit_file = read_fit_file(fit_path)
    records = get_messages_by_type(fit_file, ["RecordMessage"])
    laps = get_messages_by_type(fit_file, ["LapMessage"])
    sessions = get_messages_by_type(fit_file, ["SessionMessage"])
    events = get_messages_by_type(fit_file, ["EventMessage"])
    activities = get_messages_by_type(fit_file, ["ActivityMessage"])
    
    print_separator("Consistency Report")
    
    if not sessions:
        print("Error: No SessionMessage found.")
        return

    s = sessions[0]
    print(f"Session Start : {s.start_time}")
    print(f"Session End   : {s.timestamp}")
    if activities:
        print(f"Activity End  : {activities[0].timestamp}")
    
    if records:
        print(f"First Record  : {records[0].timestamp}")
        print(f"Last Record   : {records[-1].timestamp}")
        
        rec_dur = (records[-1].timestamp - records[0].timestamp) / 1000.0
        print(f"Record Span   : {rec_dur}s")
        
        if s.total_elapsed_time:
            diff = abs(rec_dur - s.total_elapsed_time)
            if diff > 1.0:
                print(f"WARNING: Record span ({rec_dur}s) differs from Session total_elapsed_time ({s.total_elapsed_time}s) by {diff}s")
            else:
                print(f"OK: Record span matches session duration.")

    for i, lap in enumerate(laps):
        lap_records = [r for r in records if lap.start_time <= r.timestamp <= lap.timestamp]
        print(f"Lap {i}: records={len(lap_records)}, elapsed={lap.total_elapsed_time}s")
        if lap_records:
            l_dur = (lap_records[-1].timestamp - lap_records[0].timestamp) / 1000.0
            if abs(l_dur - lap.total_elapsed_time) > 1.0:
                 print(f"  WARNING: Lap {i} duration mismatch: Record span {l_dur}s vs field {lap.total_elapsed_time}s")

def do_compare(path1: str, path2: str):
    print(f"Comparing:\n  1: {path1}\n  2: {path2}")
    fit1 = read_fit_file(path1)
    fit2 = read_fit_file(path2)
    
    def get_summary_dict(fit_file):
        msgs = {}
        # Track FileId, Session, Activity (usually only one of each)
        for r in fit_file.records:
            m = r.message
            m_type = type(m).__name__
            if m_type in ("FileIdMessage", "SessionMessage", "ActivityMessage"):
                msgs[m_type] = {f.name: f.get_value() for f in m.fields if f.get_value() is not None}
        return msgs

    sum1 = get_summary_dict(fit1)
    sum2 = get_summary_dict(fit2)
    
    all_types = set(sum1.keys()) | set(sum2.keys())
    
    for mtype in sorted(all_types):
        print_separator(f"Comparison: {mtype}")
        if mtype not in sum1:
            print(f"Message {mtype} only in File 2")
            continue
        if mtype not in sum2:
            print(f"Message {mtype} only in File 1")
            continue
            
        d1 = sum1[mtype]
        d2 = sum2[mtype]
        
        all_fields = set(d1.keys()) | set(d2.keys())
        for field in sorted(all_fields):
            v1 = d1.get(field)
            v2 = d2.get(field)
            if v1 != v2:
                print(f"{field:25}: {v1} -> {v2}")

def do_compare_fields(path1: str, path2: str):
    print(f"Comparing Fields availability:\n  1: {path1}\n  2: {path2}")
    fit1 = read_fit_file(path1)
    fit2 = read_fit_file(path2)

    def get_all_fields(fit_file):
        fields_by_type = {}
        for r in fit_file.records:
            m = r.message
            if type(m).__name__ == "DefinitionMessage" or not hasattr(m, "fields"):
                continue
            m_type = type(m).__name__
            if m_type not in fields_by_type:
                fields_by_type[m_type] = set()
            for f in m.fields:
                if f.get_value() is not None:
                    fields_by_type[m_type].add(f.name)
        return fields_by_type

    f1 = get_all_fields(fit1)
    f2 = get_all_fields(fit2)

    all_types = set(f1.keys()) | set(f2.keys())

    for mtype in sorted(all_types):
        print_separator(f"Field Availability: {mtype}")
        if mtype not in f1:
            print(f"Message {mtype} ONLY in File 2")
            continue
        if mtype not in f2:
            print(f"Message {mtype} ONLY in File 1")
            continue

        s1 = f1[mtype]
        s2 = f2[mtype]

        only1 = s1 - s2
        only2 = s2 - s1
        common = s1 & s2

        if only1:
            print(f"  Fields only in File 1: {sorted(list(only1))}")
        if only2:
            print(f"  Fields only in File 2: {sorted(list(only2))}")
        if not only1 and not only2:
            print(f"  All fields match ({len(common)} fields)")
        else:
            print(f"  Common fields ({len(common)}): {sorted(list(common))}")

def main():
    parser = argparse.ArgumentParser(description="Analyze and compare FIT files.")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Summary
    sum_parser = subparsers.add_parser("summary", help="Show summary of messages")
    sum_parser.add_argument("file", help="Path to FIT file")
    
    # Inspect
    ins_parser = subparsers.add_parser("inspect", help="Detailed view of messages")
    ins_parser.add_argument("file", help="Path to FIT file")
    ins_parser.add_argument("-t", "--types", nargs="+", help="Specific message types to show (e.g. SessionMessage)")
    ins_parser.add_argument("-n", "--limit", type=int, default=0, help="Limit number of messages per type")
    
    # Consistency
    con_parser = subparsers.add_parser("consistency", help="Check for timing consistency")
    con_parser.add_argument("file", help="Path to FIT file")
    
    # Compare
    cmp_parser = subparsers.add_parser("compare", help="Compare values in key messages (FileId, Session, Activity)")
    cmp_parser.add_argument("file1", help="First FIT file")
    cmp_parser.add_argument("file2", help="Second FIT file")

    # Compare Fields
    cmpf_parser = subparsers.add_parser("compare-fields", help="Compare which fields are present in ALL message types")
    cmpf_parser.add_argument("file1", help="First FIT file")
    cmpf_parser.add_argument("file2", help="Second FIT file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    if args.command == "summary":
        do_summary(args.file)
    elif args.command == "inspect":
        do_inspect(args.file, args.types, args.limit)
    elif args.command == "consistency":
        do_consistency(args.file)
    elif args.command == "compare":
        do_compare(args.file1, args.file2)
    elif args.command == "compare-fields":
        do_compare_fields(args.file1, args.file2)

if __name__ == "__main__":
    main()
