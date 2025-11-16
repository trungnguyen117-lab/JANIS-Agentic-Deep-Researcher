"use client";

import React, { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PlanOutline as PlanOutlineType, Section, SubSection } from "../../types/types";
import { GripVertical, Plus, Trash2, Edit2, Save, X } from "lucide-react";
import styles from "./PlanOutline.module.scss";

interface PlanOutlineProps {
  outline: PlanOutlineType;
  onOutlineChange?: (outline: PlanOutlineType) => void;
  onSave?: (outline: PlanOutlineType) => void;
  editable?: boolean;
}

export const PlanOutline: React.FC<PlanOutlineProps> = ({
  outline,
  onOutlineChange,
  onSave,
  editable = true,
}) => {
  console.log("[PlanOutline] Component rendered with outline:", outline);
  console.log("[PlanOutline] Outline sections:", outline?.sections);
  console.log("[PlanOutline] Editable:", editable);
  
  const [localOutline, setLocalOutline] = useState<PlanOutlineType>(outline);
  const [editingSectionId, setEditingSectionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editEstimatedDepth, setEditEstimatedDepth] = useState("");
  const [editingSubsectionId, setEditingSubsectionId] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  
  // Log when outline prop changes
  React.useEffect(() => {
    console.log("[PlanOutline] Outline prop changed:", outline);
    if (outline) {
      // Only update if the outline actually changed (deep comparison would be better, but JSON.stringify is simpler)
      const currentOutlineStr = JSON.stringify(localOutline);
      const newOutlineStr = JSON.stringify(outline);
      if (currentOutlineStr !== newOutlineStr) {
        setLocalOutline(outline);
        console.log("[PlanOutline] Updated localOutline with", outline.sections?.length, "sections");
        // Auto-expand sections that have subsections
        const sectionsWithSubsections = outline.sections
          .filter((s) => s.subsections && s.subsections.length > 0)
          .map((s) => s.id);
        if (sectionsWithSubsections.length > 0) {
          setExpandedSections(new Set(sectionsWithSubsections));
          console.log("[PlanOutline] Auto-expanded sections with subsections:", sectionsWithSubsections);
        }
      }
    }
  }, [outline]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSectionUpdate = useCallback(
    (sectionId: string, updates: Partial<Section>) => {
      setLocalOutline((prevOutline) => {
        const updatedSections = prevOutline.sections.map((section) =>
          section.id === sectionId ? { ...section, ...updates } : section
        );
        const updatedOutline = { ...prevOutline, sections: updatedSections };
        // Only call onOutlineChange if it's provided and we're not just syncing from prop
        // This prevents infinite loops when outline prop updates
        if (onOutlineChange && JSON.stringify(prevOutline) !== JSON.stringify(updatedOutline)) {
          onOutlineChange(updatedOutline);
        }
        return updatedOutline;
      });
    },
    [onOutlineChange]
  );

  const handleAddSection = useCallback(() => {
    setLocalOutline((prevOutline) => {
      const newOrder = Math.max(...prevOutline.sections.map((s) => s.order), 0) + 1;
      const newSection: Section = {
        id: `section_${Date.now()}`,
        title: "New Section",
        description: "Section description",
        order: newOrder,
        estimatedDepth: "2-3 pages",
        subsections: [],
      };
      const updatedSections = [...prevOutline.sections, newSection];
      const updatedOutline = { ...prevOutline, sections: updatedSections };
      onOutlineChange?.(updatedOutline);
      setEditingSectionId(newSection.id);
      setEditTitle(newSection.title);
      setEditDescription(newSection.description);
      setExpandedSections((prev) => new Set(prev).add(newSection.id));
      return updatedOutline;
    });
  }, [onOutlineChange]);

  const handleAddSubsection = useCallback((sectionId: string) => {
    setLocalOutline((prevOutline) => {
      const section = prevOutline.sections.find((s) => s.id === sectionId);
      if (!section) return prevOutline;
      
      const subsections = section.subsections || [];
      const newOrder = Math.max(...subsections.map((ss) => ss.order), 0) + 1;
      const newSubsection: SubSection = {
        id: `subsection_${sectionId}_${Date.now()}`,
        title: "New Subsection",
        description: "Subsection description",
        order: newOrder,
      };
      
      const updatedSections = prevOutline.sections.map((s) =>
        s.id === sectionId
          ? { ...s, subsections: [...subsections, newSubsection] }
          : s
      );
      const updatedOutline = { ...prevOutline, sections: updatedSections };
      onOutlineChange?.(updatedOutline);
      setEditingSubsectionId(newSubsection.id);
      return updatedOutline;
    });
  }, [onOutlineChange]);

  const handleDeleteSubsection = useCallback((sectionId: string, subsectionId: string) => {
    setLocalOutline((prevOutline) => {
      const updatedSections = prevOutline.sections.map((s) => {
        if (s.id === sectionId) {
          const subsections = (s.subsections || []).filter((ss) => ss.id !== subsectionId);
          // Reorder remaining subsections
          const reorderedSubsections = subsections.map((ss, index) => ({
            ...ss,
            order: index + 1,
          }));
          return { ...s, subsections: reorderedSubsections };
        }
        return s;
      });
      const updatedOutline = { ...prevOutline, sections: updatedSections };
      onOutlineChange?.(updatedOutline);
      return updatedOutline;
    });
  }, [onOutlineChange]);

  const handleSubsectionUpdate = useCallback((sectionId: string, subsectionId: string, updates: Partial<SubSection>) => {
    setLocalOutline((prevOutline) => {
      const updatedSections = prevOutline.sections.map((s) => {
        if (s.id === sectionId) {
          const subsections = (s.subsections || []).map((ss) =>
            ss.id === subsectionId ? { ...ss, ...updates } : ss
          );
          return { ...s, subsections };
        }
        return s;
      });
      const updatedOutline = { ...prevOutline, sections: updatedSections };
      onOutlineChange?.(updatedOutline);
      return updatedOutline;
    });
  }, [onOutlineChange]);

  const toggleSectionExpanded = useCallback((sectionId: string) => {
    setExpandedSections((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(sectionId)) {
        newSet.delete(sectionId);
      } else {
        newSet.add(sectionId);
      }
      return newSet;
    });
  }, []);

  const handleDeleteSection = useCallback(
    (sectionId: string) => {
      setLocalOutline((prevOutline) => {
        const updatedSections = prevOutline.sections.filter((s) => s.id !== sectionId);
        // Reorder remaining sections
        const reorderedSections = updatedSections.map((s, index) => ({
          ...s,
          order: index + 1,
        }));
        const updatedOutline = { ...prevOutline, sections: reorderedSections };
        onOutlineChange?.(updatedOutline);
        return updatedOutline;
      });
    },
    [onOutlineChange]
  );

  const handleStartEdit = useCallback((section: Section) => {
    setEditingSectionId(section.id);
    setEditTitle(section.title);
    setEditDescription(section.description);
    setEditEstimatedDepth(section.estimatedDepth || "2-3 pages");
  }, []);

  const handleSaveEdit = useCallback(() => {
    if (editingSectionId) {
      const section = localOutline.sections.find((s) => s.id === editingSectionId);
      handleSectionUpdate(editingSectionId, {
        title: editTitle,
        description: editDescription,
        estimatedDepth: editEstimatedDepth || undefined,
        // Preserve subsections when editing
        subsections: section?.subsections || [],
      });
      setEditingSectionId(null);
    }
  }, [editingSectionId, editTitle, editDescription, editEstimatedDepth, localOutline.sections, handleSectionUpdate]);

  const handleCancelEdit = useCallback(() => {
    setEditingSectionId(null);
    setEditTitle("");
    setEditDescription("");
    setEditEstimatedDepth("");
  }, []);

  const handleMoveUp = useCallback(
    (index: number) => {
      if (index === 0) return;
      const sections = [...localOutline.sections];
      [sections[index - 1], sections[index]] = [sections[index], sections[index - 1]];
      const reorderedSections = sections.map((s, i) => ({ ...s, order: i + 1 }));
      const updatedOutline = { ...localOutline, sections: reorderedSections };
      setLocalOutline(updatedOutline);
      onOutlineChange?.(updatedOutline);
    },
    [localOutline, onOutlineChange]
  );

  const handleMoveDown = useCallback(
    (index: number) => {
      if (index === localOutline.sections.length - 1) return;
      const sections = [...localOutline.sections];
      [sections[index], sections[index + 1]] = [sections[index + 1], sections[index]];
      const reorderedSections = sections.map((s, i) => ({ ...s, order: i + 1 }));
      const updatedOutline = { ...localOutline, sections: reorderedSections };
      setLocalOutline(updatedOutline);
      onOutlineChange?.(updatedOutline);
    },
    [localOutline, onOutlineChange]
  );

  const sortedSections = [...localOutline.sections].sort((a, b) => a.order - b.order);
  
  console.log("[PlanOutline] Sorted sections:", sortedSections.map(s => ({ id: s.id, title: s.title, order: s.order })));
  console.log("[PlanOutline] Rendering", sortedSections.length, "section cards");

  console.log("[PlanOutline] Rendering container with", sortedSections.length, "sections");
  
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>Document Outline</h3>
        {editable && (
          <div className={styles.headerActions}>
            <Button
              onClick={handleAddSection}
              size="sm"
              variant="outline"
              className={styles.addButton}
            >
              <Plus size={16} />
              Add Section
            </Button>
            {onSave && (
              <Button
                onClick={() => onSave(localOutline)}
                size="sm"
                className={styles.saveButton}
              >
                <Save size={16} />
                Save Outline
              </Button>
            )}
          </div>
        )}
      </div>
      <div className={styles.sectionsList}>
        {sortedSections.length === 0 ? (
          console.warn("[PlanOutline] ⚠️ No sections to render!") || <div>No sections found</div>
        ) : (
          sortedSections.map((section, index) => {
            console.log(`[PlanOutline] Rendering section ${index + 1}/${sortedSections.length}:`, section.id, section.title);
            return (
              <div key={section.id} className={styles.sectionCard}>
            <div className={styles.sectionHeader}>
              <div className={styles.sectionNumber}>{section.order}</div>
              {editable && (
                <div className={styles.sectionActions}>
                  <Button
                    onClick={() => handleMoveUp(index)}
                    size="sm"
                    variant="ghost"
                    disabled={index === 0}
                    className={styles.moveButton}
                  >
                    ↑
                  </Button>
                  <Button
                    onClick={() => handleMoveDown(index)}
                    size="sm"
                    variant="ghost"
                    disabled={index === sortedSections.length - 1}
                    className={styles.moveButton}
                  >
                    ↓
                  </Button>
                  {editingSectionId !== section.id && (
                    <>
                      <Button
                        onClick={() => handleStartEdit(section)}
                        size="sm"
                        variant="ghost"
                        className={styles.editButton}
                      >
                        <Edit2 size={14} />
                      </Button>
                      <Button
                        onClick={() => handleDeleteSection(section.id)}
                        size="sm"
                        variant="ghost"
                        className={styles.deleteButton}
                      >
                        <Trash2 size={14} />
                      </Button>
                    </>
                  )}
                </div>
              )}
            </div>
            {editingSectionId === section.id ? (
              <div className={styles.editForm}>
                <Input
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  placeholder="Section title"
                  className={styles.editInput}
                />
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Section description"
                  className={styles.editTextarea}
                  rows={3}
                />
                <Input
                  value={editEstimatedDepth}
                  onChange={(e) => setEditEstimatedDepth(e.target.value)}
                  placeholder="Estimated length (e.g., 2-3 pages, 1500 words)"
                  className={styles.editInput}
                />
                <div className={styles.editActions}>
                  <Button onClick={handleSaveEdit} size="sm" variant="default">
                    <Save size={14} />
                    Save
                  </Button>
                  <Button onClick={handleCancelEdit} size="sm" variant="ghost">
                    <X size={14} />
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className={styles.sectionContent}>
                <div className={styles.sectionHeaderContent}>
                  <div className={styles.sectionTitleContainer}>
                    <h4 className={styles.sectionTitle}>{section.title}</h4>
                    {section.subsections && section.subsections.length > 0 && (
                      <span className={styles.subsectionsBadge}>
                        {section.subsections.length} {section.subsections.length === 1 ? 'subsection' : 'subsections'}
                      </span>
                    )}
                  </div>
                  {editable && (
                    <Button
                      onClick={() => toggleSectionExpanded(section.id)}
                      size="sm"
                      variant="ghost"
                      className={styles.expandButton}
                    >
                      {expandedSections.has(section.id) ? "▼" : "▶"}
                    </Button>
                  )}
                </div>
                <p className={styles.sectionDescription}>{section.description}</p>
                <div className={styles.sectionMeta}>
                  <span className={styles.metaLabel}>Estimated Length:</span>
                  <span>{section.estimatedDepth || "2-3 pages (default)"}</span>
                </div>
                
                {/* Subsections */}
                {section.subsections && section.subsections.length > 0 && (
                  <div className={styles.subsectionsContainer}>
                    <div className={styles.subsectionsHeader}>
                      <span className={styles.subsectionsLabel}>
                        Subsections ({section.subsections.length})
                      </span>
                      {editable && expandedSections.has(section.id) && (
                        <Button
                          onClick={() => handleAddSubsection(section.id)}
                          size="sm"
                          variant="outline"
                          className={styles.addSubsectionButton}
                        >
                          <Plus size={12} />
                          Add Subsection
                        </Button>
                      )}
                    </div>
                    {expandedSections.has(section.id) && (
                      <div className={styles.subsectionsList}>
                        {[...section.subsections].sort((a, b) => a.order - b.order).map((subsection) => (
                          <div key={subsection.id} className={styles.subsectionCard}>
                            {editingSubsectionId === subsection.id ? (
                              <SubsectionEditForm
                                subsection={subsection}
                                onSave={(updates) => {
                                  handleSubsectionUpdate(section.id, subsection.id, updates);
                                  setEditingSubsectionId(null);
                                }}
                                onCancel={() => setEditingSubsectionId(null)}
                              />
                            ) : (
                              <>
                                <div className={styles.subsectionContent}>
                                  <div className={styles.subsectionHeader}>
                                    <span className={styles.subsectionNumber}>{subsection.order}</span>
                                    <h5 className={styles.subsectionTitle}>{subsection.title}</h5>
                                  </div>
                                  <p className={styles.subsectionDescription}>{subsection.description}</p>
                                </div>
                                {editable && (
                                  <div className={styles.subsectionActions}>
                                    <Button
                                      onClick={() => setEditingSubsectionId(subsection.id)}
                                      size="sm"
                                      variant="ghost"
                                      className={styles.editButton}
                                    >
                                      <Edit2 size={12} />
                                    </Button>
                                    <Button
                                      onClick={() => handleDeleteSubsection(section.id, subsection.id)}
                                      size="sm"
                                      variant="ghost"
                                      className={styles.deleteButton}
                                    >
                                      <Trash2 size={12} />
                                    </Button>
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Show "Add Subsection" button if section has no subsections */}
                {editable && expandedSections.has(section.id) && (!section.subsections || section.subsections.length === 0) && (
                  <Button
                    onClick={() => handleAddSubsection(section.id)}
                    size="sm"
                    variant="outline"
                    className={styles.addSubsectionButton}
                  >
                    <Plus size={12} />
                    Add Subsection
                  </Button>
                )}
              </div>
            )}
          </div>
            );
          })
        )}
      </div>
      {localOutline.metadata && (
        <div className={styles.metadata}>
          {localOutline.metadata.totalSections && (
            <span>Total Sections: {localOutline.metadata.totalSections}</span>
          )}
          {localOutline.metadata.estimatedTotalPages && (
            <span>Estimated Pages: {localOutline.metadata.estimatedTotalPages}</span>
          )}
        </div>
      )}
    </div>
  );
};

// Subsection Edit Form Component
interface SubsectionEditFormProps {
  subsection: SubSection;
  onSave: (updates: Partial<SubSection>) => void;
  onCancel: () => void;
}

const SubsectionEditForm: React.FC<SubsectionEditFormProps> = ({ subsection, onSave, onCancel }) => {
  const [editTitle, setEditTitle] = useState(subsection.title);
  const [editDescription, setEditDescription] = useState(subsection.description);

  const handleSave = () => {
    onSave({
      title: editTitle,
      description: editDescription,
    });
  };

  return (
    <div className={styles.subsectionEditForm}>
      <Input
        value={editTitle}
        onChange={(e) => setEditTitle(e.target.value)}
        placeholder="Subsection title"
        className={styles.editInput}
      />
      <textarea
        value={editDescription}
        onChange={(e) => setEditDescription(e.target.value)}
        placeholder="Subsection description"
        className={styles.editTextarea}
        rows={2}
      />
      <div className={styles.editActions}>
        <Button onClick={handleSave} size="sm" variant="default">
          <Save size={12} />
          Save
        </Button>
        <Button onClick={onCancel} size="sm" variant="ghost">
          <X size={12} />
          Cancel
        </Button>
      </div>
    </div>
  );
};

