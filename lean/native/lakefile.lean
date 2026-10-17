import Lake
open Lake DSL

package maam_paper_export

lean_exe «maam-paper-export» where
  root := `PaperExport
  supportInterpreter := true
