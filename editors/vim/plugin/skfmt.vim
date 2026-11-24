" skfmt.vim - format SKILL buffers with the skfmt CLI.
" Requires Vim 7.4 or newer.

if v:version < 704
  echohl ErrorMsg
  echomsg 'skfmt.vim requires Vim 7.4 or newer'
  echohl None
  finish
endif

if exists('g:loaded_skfmt')
  finish
endif
let g:loaded_skfmt = 1

command! -nargs=0 Skfmt call skfmt#FormatAll()
command! -range=% -nargs=0 SkfmtRange call skfmt#FormatRange(<line1>, <line2>)
command! -nargs=0 SkfmtRefresh call skfmt#Refresh()
command! -nargs=0 SkfmtVersion call skfmt#Version()
