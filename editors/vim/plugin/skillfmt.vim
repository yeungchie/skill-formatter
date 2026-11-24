" skillfmt.vim - format SKILL buffers with the skill-formatter CLI.
" Requires Vim 7.4 or newer.

if v:version < 704
  echohl ErrorMsg
  echomsg 'skillfmt.vim requires Vim 7.4 or newer'
  echohl None
  finish
endif

if exists('g:loaded_skillfmt')
  finish
endif
let g:loaded_skillfmt = 1

command! -nargs=0 Skillfmt call skillfmt#FormatAll()
command! -range=% -nargs=0 SkillfmtRange call skillfmt#FormatRange(<line1>, <line2>)
command! -nargs=0 SkillfmtRefresh call skillfmt#Refresh()
command! -nargs=0 SkillfmtVersion call skillfmt#Version()
