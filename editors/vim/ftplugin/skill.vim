setlocal commentstring=;%s

let s:exe = get(g:, 'skfmt_executable', 'skfmt')
if executable(s:exe)
  call skfmt#Setup()
endif
unlet s:exe
