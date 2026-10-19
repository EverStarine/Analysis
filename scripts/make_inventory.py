#!/usr/bin/env python3
"""Build the Analysis source heading inventory for selected volumes.

Purpose: compare active source titles and hierarchy with PDF bookmarks; write
only heading-inventory.json to --out-dir, without task baselines or PDF copies.
Reassess the parser when project layout or heading/input macros change.
The default project root is resolved from this file's scripts/ location.
"""
from pathlib import Path
import argparse
import re, json, hashlib
from collections import Counter

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
LEVELS = {'volume':0, 'part':1, 'chapter':2, 'section':3, 'subsection':4, 'subsubsection':5, 'paragraph':6, 'subparagraph':7}

def strip_comments(s):
    return re.sub(r'(?<!\\)%[^\n]*', lambda m:' '*len(m.group()), s)

def group(s, pos, opening='{', closing='}'):
    while pos < len(s) and s[pos].isspace(): pos += 1
    if pos >= len(s) or s[pos] != opening: return None, pos
    start, depth = pos+1, 1
    pos += 1
    while pos < len(s):
        if s[pos]=='\\':
            pos += 2
            continue
        if s[pos] == opening: depth += 1
        elif s[pos] == closing:
            depth -= 1
            if depth == 0: return s[start:pos], pos+1
        pos += 1
    raise ValueError('Unclosed argument')

def display(s):
    s = s.replace('\\\\', ' ')
    # Keep meaningful TeX in mathematical title text; remove only rendering wrappers.
    pat = re.compile(r'\\texorpdfstring\s*')
    while m:=pat.search(s):
        a,p=group(s,m.end()); b,q=group(s,p)
        if a is None or b is None: break
        s=s[:m.start()]+a+s[q:]
    return re.sub(r'\s+',' ',s).strip()

def make_inventory(project_root, volumes):
    ROOT = project_root
    records=[]; files={}; visits=[]; errors=[]
    for book in volumes:
        base=ROOT/f'Book{book}'; root=base/f'Book{book}.tex'
        raw=root.read_text(encoding='utf-8-sig')
        m=re.search(r'\\newcommand\{\\BookTitle\}',raw)
        title,p=group(raw,m.end())
        vol={'id':f'b{book}:volume','book':book,'level':'volume','command':'BookTitle','title':display(title),'raw_title':title,'file':root.relative_to(ROOT).as_posix(),'line':raw.count('\n',0,m.start())+1,'label':None,'optional':False,'starred':False,'functional':False,'order':len(records),'parent_id':None,'children_ids':[]}
        records.append(vol); stack=[vol]; bookrecords=[vol]
        def add(level,command,title,label,file,line,optional=False,starred=False,functional=False):
            depth=LEVELS[level]
            while len(stack)>1 and LEVELS[stack[-1]['level']]>=depth: stack.pop()
            parent=stack[-1]
            rid=label or f'{file}:{line}:{command}'
            r={'id':rid,'book':book,'level':level,'command':command,'title':display(title),'raw_title':title,'file':file,'line':line,'label':label,'optional':optional,'starred':starred,'functional':functional,'order':len(records),'parent_id':parent['id'],'children_ids':[]}
            parent['children_ids'].append(rid); records.append(r); bookrecords.append(r); stack.append(r)
        def visit(path):
            path=path.resolve(); rel=path.relative_to(ROOT).as_posix()
            raw=path.read_text(encoding='utf-8-sig'); s=strip_comments(raw)
            files[rel]=hashlib.sha256(path.read_bytes()).hexdigest(); visits.append(rel)
            pos=0
            token=re.compile(r'\\([A-Za-z]+)(\*)?')
            while m:=token.search(s,pos):
                cmd=m.group(1); star=bool(m.group(2)); pos=m.end()
                line=s.count('\n',0,m.start())+1
                if cmd in ('frontmatter','mainmatter','backmatter'):
                    stack[:]=[vol]; continue
                if cmd=='input':
                    arg,pos=group(s,pos)
                    if arg is None: continue
                    if arg.startswith('../Shared'): continue
                    targets=[base/(arg if Path(arg).suffix else arg+'.tex'),path.parent/(arg if Path(arg).suffix else arg+'.tex')]
                    target=next((t for t in targets if t.is_file()),None)
                    if target is None: errors.append({'file':rel,'line':line,'input':arg}); continue
                    visit(target); continue
                if cmd in ('newcommand','renewcommand','providecommand','NewDocumentCommand','RenewDocumentCommand'):
                    # Project-root metadata/macros are not printed headings.
                    a,pos2=group(s,pos)
                    if a is not None:
                        pos=pos2
                        opt,pos2=group(s,pos,'[',']')
                        if opt is not None: pos=pos2
                        a,pos2=group(s,pos)
                        if a is not None: pos=pos2
                        if cmd.endswith('DocumentCommand'):
                            a,pos2=group(s,pos)
                            if a is not None: pos=pos2
                    continue
                if cmd=='MakeBookTitle':
                    opt,pos2=group(s,pos,'[',']')
                    if opt is not None: pos=pos2
                    continue
                level=None; title=None; label=None; optional=False; functional=False
                if cmd in LEVELS and cmd!='volume':
                    short,pos2=group(s,pos,'[',']')
                    if short is not None: pos=pos2
                    title,pos=group(s,pos); level=cmd
                    if title is None: continue
                    immediate=re.match(r'\s*\\label\s*',s[pos:])
                    if immediate: label,_=group(s,pos+immediate.end())
                    functional=star and title in ('序言','后记','参考文献','习题')
                elif cmd in ('OptionalChapter','OptionalSection','OptionalSubsection'):
                    if cmd=='OptionalChapter':
                        short,pos2=group(s,pos,'[',']')
                        if short is not None: pos=pos2
                    title,pos=group(s,pos); label,pos=group(s,pos)
                    level=cmd.removeprefix('Optional').lower(); optional=True
                elif cmd=='BookPart':
                    title,pos=group(s,pos); label,pos=group(s,pos); level='part'
                elif cmd=='BookAppendixPart':
                    label,pos=group(s,pos); title='附录'; level='part'; functional=True; star=True
                elif cmd=='BookPartGuide':
                    short,pos2=group(s,pos,'[',']')
                    if short is not None: pos=pos2
                    title=short or '本编导读'; level='chapter'; functional=True; star=True
                elif cmd=='BookExercises':
                    title='习题'; level='section'; functional=True; star=True
                elif cmd=='PrintBookIndex':
                    kind,pos=group(s,pos); title,pos=group(s,pos); level='chapter'; functional=True; star=True
                elif cmd in ('MakeBookContents','tableofcontents','MakeBookListOfTables','listoftables','listoffigures'):
                    title={'MakeBookContents':'目录','tableofcontents':'目录','MakeBookListOfTables':'表目录','listoftables':'表目录','listoffigures':'图目录'}[cmd]
                    level='chapter'; functional=True; star=True
                if level and title is not None:
                    add(level,cmd,title,label,rel,line,optional,star,functional)
        visit(root)
        # Scope ends at next heading of same/higher level, regardless of source-file split.
        for i,r in enumerate(bookrecords):
            nxt=next((x for x in bookrecords[i+1:] if LEVELS[x['level']]<=LEVELS[r['level']]),None)
            r['body_range']={'start':f"{r['file']}:{r['line']}",'end_before_id':nxt['id'] if nxt else None,'scope':'active input order'}

    ids=[r['id'] for r in records]
    duplicates=[k for k,v in Counter(ids).items() if v>1]
    if errors or duplicates: raise ValueError({'input_errors':errors,'duplicate_ids':duplicates})
    return {'description':'Active printed headings in recursively expanded input order, including functional macro headings; Shared definitions excluded.',
            'project_root':str(ROOT), 'volumes':volumes, 'headings':records,
            'counts':{str(b):dict(Counter(r['level'] for r in records if r['book']==b)) for b in volumes},
            'functional_counts':{str(b):sum(r['functional'] for r in records if r['book']==b) for b in volumes},
            'active_files':sorted(files),'source_hashes':files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=DEFAULT_ROOT,
                        help='Project or isolated source root; default is the parent of scripts/')
    parser.add_argument('--volumes', type=int, nargs='+', choices=[1, 2, 3], default=[1, 2, 3])
    parser.add_argument('--out-dir', type=Path, required=True,
                        help='Explicit directory for heading-inventory.json')
    args = parser.parse_args()
    data = make_inventory(args.project_root.resolve(), sorted(set(args.volumes)))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    target = args.out_dir / 'heading-inventory.json'
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'total':len(data['headings']), 'counts':data['counts'],
                      'functional_counts':data['functional_counts'],
                      'active_files':len(data['active_files']), 'inventory':str(target.resolve())},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
