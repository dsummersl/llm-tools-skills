" lua << EOF
" require('lazy-loader')()
" EOF

let g:gutentags_ctags_exclude += ['*/.venv/*']
let g:projectionist_heuristics = {
      \ 'pyproject.toml': {
      \   'llm_tools_skills/*.py': {
      \     'type': 'function',
      \     'alternate': [
      \       'tests/{dirname}test_{basename}.py',
      \       'tests/{dirname}/test_{basename}.py',
      \     ]
      \   },
      \   'tests/**/test_*.py': {
      \     'type': 'test',
      \     'alternate': [
      \       'llm_tools_skills/{dirname}{basename}.py',
      \       'llm_tools_skills/{dirname}/{basename}.py',
      \     ]
      \   },
      \ },
      \ }
