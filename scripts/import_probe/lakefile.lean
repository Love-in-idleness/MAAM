import Lake
open Lake DSL
package maam_import_probe
lean_exe «import-probe» where
  root := `ImportProbe
  supportInterpreter := true
