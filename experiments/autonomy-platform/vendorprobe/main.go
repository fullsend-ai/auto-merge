// This probe calls Fullsend's content collectors, never its installer.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/fullsend-ai/fullsend/internal/scaffold"
)

func run() error {
	if len(os.Args) != 4 {
		return fmt.Errorf("invalid_arguments")
	}
	root, destination, revision := os.Args[1], os.Args[2], os.Args[3]
	assets, err := scaffold.CollectVendoredAssets(root, ".fullsend/")
	if err != nil {
		return err
	}
	vendored, err := scaffold.CollectPerRepoInstallFiles(true, revision, revision)
	if err != nil {
		return err
	}
	layered, err := scaffold.CollectPerRepoInstallFiles(false, revision, revision)
	if err != nil {
		return err
	}
	hashes := map[string]string{}
	marker := false
	local := false
	remote := false
	for _, file := range append(assets, vendored...) {
		path := filepath.Clean(file.Path)
		if path == "." || filepath.IsAbs(path) || strings.HasPrefix(path, "..") {
			return fmt.Errorf("unsafe_path")
		}
		if path == ".defaults/action.yml" {
			marker = true
		}
		if path == ".github/workflows/fullsend.yaml" {
			local = bytes.Contains(file.Content, []byte("uses: ./.github/workflows/reusable-dispatch.yml"))
		}
		output := filepath.Join(destination, path)
		if err := os.MkdirAll(filepath.Dir(output), 0700); err != nil {
			return err
		}
		if err := os.WriteFile(output, file.Content, 0600); err != nil {
			return err
		}
		h := sha256.Sum256(file.Content)
		hashes[path] = hex.EncodeToString(h[:])
	}
	for _, file := range layered {
		if file.Path == ".github/workflows/fullsend.yaml" {
			remote = bytes.Contains(file.Content, []byte("fullsend-ai/fullsend/.github/workflows/reusable-dispatch.yml@"+revision))
		}
	}
	if !marker || !local || !remote {
		return fmt.Errorf("unexpected_rendered_routing")
	}
	report := map[string]any{"source_commit": revision, "collector": "Fullsend CollectVendoredAssets and CollectPerRepoInstallFiles", "content_files": len(hashes), "content_sha256": hashes, "vendored_marker_present": marker, "vendored_dispatch_is_local": local, "layered_dispatch_pinned_upstream": remote, "binary_packaged": false, "installer_executed": false, "workflow_executed": false, "credentials_used": false, "mutation_permitted": false}
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(destination, "vendor-report.json"), append(data, '\n'), 0600); err != nil {
		return err
	}
	fmt.Println("Native Fullsend vendor collectors and both routing variants passed; content staged only, no binary or install.")
	return nil
}
func main() {
	if run() != nil {
		fmt.Println("vendor_probe_failed")
		os.Exit(2)
	}
}
