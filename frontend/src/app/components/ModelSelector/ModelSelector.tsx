"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Settings } from "lucide-react";
import styles from "./ModelSelector.module.scss";

const MODEL_STORAGE_KEY = "selected_model";

interface ModelInfo {
  name: string;
  input_price_per_million: number;
  output_price_per_million: number;
}

interface ModelSelectorProps {
  onModelChange?: (model: string) => void;
  tokenUsage?: { input: number; output: number; completion: number; reasoning: number; cache?: number; prompt?: number; total: number; cost?: number };
  availableModels?: ModelInfo[];
  disabled?: boolean; // Disable model selection after first message
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  onModelChange,
  tokenUsage,
  availableModels = [],
  disabled = false,
}) => {
  const [selectedModel, setSelectedModel] = useState<string>("gpt-4o");
  const [isOpen, setIsOpen] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(true);

  // Load models from models.json file
  useEffect(() => {
    const loadModels = async () => {
      try {
        const response = await fetch("/models.json");
        if (!response.ok) {
          throw new Error("Failed to load models.json");
        }
        const data = await response.json();
        const modelsList: ModelInfo[] = [];
        
        if (data.models) {
          for (const [modelName, modelConfig] of Object.entries(data.models)) {
            const config = modelConfig as any;
            modelsList.push({
              name: modelName,
              input_price_per_million: config.input_price_per_million || 0,
              output_price_per_million: config.output_price_per_million || 0,
            });
          }
        }
        
        setModels(modelsList);
        setIsLoadingModels(false);
      } catch (error) {
        console.error("Failed to load models.json:", error);
        // Fallback to availableModels from props if fetch fails
        if (availableModels.length > 0) {
          setModels(availableModels);
        } else {
          // Last resort: use default
          setModels([{ name: "gpt-4o", input_price_per_million: 1.5, output_price_per_million: 6.0 }]);
        }
        setIsLoadingModels(false);
      }
    };

    loadModels();
  }, [availableModels]);

  // Extract model names from loaded models (memoized to prevent infinite loops)
  const modelNames = useMemo(() => {
    return models.length > 0 
      ? models.map(m => m.name)
      : availableModels.length > 0
      ? availableModels.map(m => m.name)
      : ["gpt-4o"]; // Fallback if no models provided
  }, [models, availableModels]);

  useEffect(() => {
    // Load saved model from localStorage
    const savedModel = localStorage.getItem(MODEL_STORAGE_KEY);
    if (savedModel && modelNames.includes(savedModel)) {
      setSelectedModel(savedModel);
    } else if (modelNames.length > 0) {
      // If saved model not in list, use first available
      setSelectedModel(modelNames[0]);
    }
  }, [modelNames]);

  const handleModelChange = async (value: string) => {
    setSelectedModel(value);
    localStorage.setItem(MODEL_STORAGE_KEY, value);
    onModelChange?.(value);
    
    // Try to update model via API if available
    try {
      // This would require a backend endpoint to update model
      // For now, model change requires backend restart with MODEL_NAME env var
      console.log(`Model changed to: ${value}. Restart backend with MODEL_NAME=${value} to apply.`);
    } catch (error) {
      console.error("Failed to update model:", error);
    }
  };

  const formatTokenCount = (count: number) => {
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(2)}M`;
    } else if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}K`;
    }
    return count.toString();
  };

  const formatCost = (cost: number) => {
    if (cost >= 1) {
      return `$${cost.toFixed(2)}`;
    } else if (cost >= 0.01) {
      return `$${cost.toFixed(4)}`;
    } else {
      return `$${cost.toFixed(6)}`;
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.label}>
        <Settings size={16} />
        <span>Model</span>
      </div>
      <select
        value={selectedModel}
        onChange={(e) => handleModelChange(e.target.value)}
        className={styles.select}
        disabled={disabled}
        title={disabled ? "Model can only be changed before sending the first message" : "Select model"}
      >
        {modelNames.map((model) => (
          <option key={model} value={model}>
            {model}
          </option>
        ))}
      </select>
      {tokenUsage !== undefined && (
        <div className={styles.tokenUsage}>
          <span className={styles.tokenLabel}>Tokens:</span>
          <span className={styles.tokenCount}>
            <span
              className={styles.inputTokenCount}
              title={`Input: ${formatTokenCount(tokenUsage.input)}\n  = Prompt: ${formatTokenCount(tokenUsage.prompt ?? 0)} + Cache: ${formatTokenCount(tokenUsage.cache ?? 0)}`}
            >
              {formatTokenCount(tokenUsage.input)} in
              {tokenUsage.prompt !== undefined && tokenUsage.cache !== undefined && (tokenUsage.prompt > 0 || tokenUsage.cache > 0) && (
                <span style={{ fontSize: '0.85em', opacity: 0.7 }}>
                  {" "}({formatTokenCount(tokenUsage.prompt)} prompt + {formatTokenCount(tokenUsage.cache)} cache)
                </span>
              )}
            </span>
            {" / "}
            <span 
              className={styles.outputTokenCount}
              title={`Output: ${formatTokenCount(tokenUsage.output)}\nCompletion: ${formatTokenCount(tokenUsage.completion)}\nReasoning: ${formatTokenCount(tokenUsage.reasoning)}`}
            >
              {formatTokenCount(tokenUsage.output)} out
            </span>
          </span>
          <span className={styles.cost}>
            • Cost: {formatCost(tokenUsage.cost ?? 0)}
          </span>
        </div>
      )}
    </div>
  );
};

