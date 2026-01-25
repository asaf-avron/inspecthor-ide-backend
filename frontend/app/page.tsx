"use client";

import { useState, useEffect } from "react";
import { EmptyState } from "@/components/ide/empty-state";
import { TemplateGallery } from "@/components/ide/template-gallery";
import { Button } from "@/components/ui/button";
import { FileText, FolderOpen, Save, Download, Play } from "lucide-react";

export default function Home() {
  const [showTemplateGallery, setShowTemplateGallery] = useState(false);
  const [hasProject, setHasProject] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("Untitled Specification");

  const handleChooseTemplate = () => {
    setShowTemplateGallery(true);
  };

  const handleSelectTemplate = async (templateFile: string) => {
    // Load template content
    try {
      const response = await fetch(`/templates/${templateFile}`);
      const content = await response.text();
      setSelectedTemplate(content);
      setProjectName(templateFile.replace(".md", "").replace(/-/g, " ").replace(/\b\w/g, l => l.toUpperCase()));
      setHasProject(true);
      setShowTemplateGallery(false);
    } catch (error) {
      console.error("Failed to load template:", error);
    }
  };

  const handleUploadFile = () => {
    // Create file input
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".md,.markdown";
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        const content = await file.text();
        setSelectedTemplate(content);
        setProjectName(file.name.replace(/\.md$/, ""));
        setHasProject(true);
      }
    };
    input.click();
  };

  const handleStartFromScratch = () => {
    setSelectedTemplate("# New Specification\n\n## Overview\n\nDescribe your specification here...\n");
    setProjectName("New Specification");
    setHasProject(true);
  };

  const handleNewProject = () => {
    setHasProject(false);
    setSelectedTemplate(null);
    setProjectName("Untitled Specification");
  };

  const handleDownload = () => {
    if (!selectedTemplate) return;
    const blob = new Blob([selectedTemplate], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${projectName}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!hasProject) {
    return (
      <>
        <EmptyState
          onChooseTemplate={handleChooseTemplate}
          onUploadFile={handleUploadFile}
          onStartFromScratch={handleStartFromScratch}
        />
        {showTemplateGallery && (
          <TemplateGallery
            onSelectTemplate={handleSelectTemplate}
            onClose={() => setShowTemplateGallery(false)}
          />
        )}
      </>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header with Actions */}
      <div className="flex h-14 items-center justify-between border-b px-4">
        <div className="flex items-center gap-4">
          <h1 className="text-lg font-semibold">Guardian Gateway IDE</h1>
          <span className="text-sm text-muted-foreground">|</span>
          <span className="text-sm text-muted-foreground">{projectName}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleNewProject}>
            <FileText className="mr-2 h-4 w-4" />
            New
          </Button>
          <Button variant="outline" size="sm" onClick={handleUploadFile}>
            <FolderOpen className="mr-2 h-4 w-4" />
            Open
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowTemplateGallery(true)}>
            <FileText className="mr-2 h-4 w-4" />
            Templates
          </Button>
          <Button variant="outline" size="sm" onClick={handleDownload}>
            <Download className="mr-2 h-4 w-4" />
            Download
          </Button>
          <Button variant="default" size="sm">
            <Play className="mr-2 h-4 w-4" />
            Generate Formal Spec
          </Button>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Panel - Requirements */}
        <div className="w-1/2 border-r p-4 overflow-auto">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Requirements (Markdown)</h2>
            <Button variant="ghost" size="sm">Edit</Button>
          </div>
          <div className="rounded-lg border bg-card p-6">
            <pre className="whitespace-pre-wrap text-sm font-mono">{selectedTemplate}</pre>
          </div>
        </div>

        {/* Right Panel - Generated Dafny (Placeholder) */}
        <div className="w-1/2 p-4 overflow-auto">
          <div className="mb-4">
            <h2 className="text-lg font-semibold">Generated Dafny Code</h2>
          </div>
          <div className="rounded-lg border bg-card p-6">
            <p className="text-sm text-muted-foreground">
              Click "Generate Formal Spec" to create a Dafny specification from your requirements.
            </p>
          </div>
        </div>
      </div>

      {/* Template Gallery Modal */}
      {showTemplateGallery && (
        <TemplateGallery
          onSelectTemplate={handleSelectTemplate}
          onClose={() => setShowTemplateGallery(false)}
        />
      )}
    </div>
  );
}
