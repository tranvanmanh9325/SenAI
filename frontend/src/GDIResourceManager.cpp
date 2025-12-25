#include "GDIResourceManager.h"
#include <sstream>
#include <iomanip>

GDIFontPtr GDIResourceManager::CreateFont(
    int height, int width, int escapement, int orientation,
    int weight, BOOL italic, BOOL underline, BOOL strikeOut,
    DWORD charset, DWORD outputPrecision, DWORD clipPrecision,
    DWORD quality, DWORD pitchAndFamily, const wchar_t* faceName) {
    
    std::string key = MakeFontKey(height, width, weight, italic, faceName);
    
    // Check cache first
    auto it = fontCache_.find(key);
    if (it != fontCache_.end()) {
        // Return a new instance (can't share the same font handle)
        // But we can reuse the creation parameters
        HFONT font = CreateFontW(height, width, escapement, orientation,
                                weight, italic, underline, strikeOut,
                                charset, outputPrecision, clipPrecision,
                                quality, pitchAndFamily, faceName);
        return std::make_unique<GDIFont>(font);
    }
    
    // Create new font
    HFONT font = CreateFontW(height, width, escapement, orientation,
                            weight, italic, underline, strikeOut,
                            charset, outputPrecision, clipPrecision,
                            quality, pitchAndFamily, faceName);
    
    if (font) {
        // Cache the parameters (not the handle, as fonts can't be shared)
        fontCache_[key] = std::make_unique<GDIFont>(CreateFontW(
            height, width, escapement, orientation, weight, italic,
            underline, strikeOut, charset, outputPrecision, clipPrecision,
            quality, pitchAndFamily, faceName));
    }
    
    return std::make_unique<GDIFont>(font);
}

GDIBrushPtr GDIResourceManager::CreateSolidBrush(COLORREF color) {
    std::string key = MakeBrushKey(color);
    
    // Check cache first
    auto it = brushCache_.find(key);
    if (it != brushCache_.end()) {
        // Create a new brush with same color (brushes can be shared but safer to create new)
        HBRUSH brush = ::CreateSolidBrush(color);
        return std::make_unique<GDIBrush>(brush);
    }
    
    // Create new brush
    HBRUSH brush = ::CreateSolidBrush(color);
    
    if (brush) {
        // Cache a reference brush
        brushCache_[key] = std::make_unique<GDIBrush>(::CreateSolidBrush(color));
    }
    
    return std::make_unique<GDIBrush>(brush);
}

GDIPenPtr GDIResourceManager::CreatePen(int style, int width, COLORREF color) {
    std::string key = MakePenKey(style, width, color);
    
    // Check cache first
    auto it = penCache_.find(key);
    if (it != penCache_.end()) {
        // Create a new pen with same parameters
        HPEN pen = ::CreatePen(style, width, color);
        return std::make_unique<GDIPen>(pen);
    }
    
    // Create new pen
    HPEN pen = ::CreatePen(style, width, color);
    
    if (pen) {
        // Cache a reference pen
        penCache_[key] = std::make_unique<GDIPen>(::CreatePen(style, width, color));
    }
    
    return std::make_unique<GDIPen>(pen);
}

GDIFontPtr GDIResourceManager::GetOrCreateFont(const std::string& key,
                                                 std::function<HFONT()> factory) {
    auto it = fontCache_.find(key);
    if (it != fontCache_.end()) {
        // Create new instance from factory
        HFONT font = factory();
        return std::make_unique<GDIFont>(font);
    }
    
    // Create and cache
    HFONT font = factory();
    if (font) {
        fontCache_[key] = std::make_unique<GDIFont>(factory());
    }
    
    return std::make_unique<GDIFont>(font);
}

GDIBrushPtr GDIResourceManager::GetOrCreateBrush(const std::string& key,
                                                   std::function<HBRUSH()> factory) {
    auto it = brushCache_.find(key);
    if (it != brushCache_.end()) {
        // Create new instance from factory
        HBRUSH brush = factory();
        return std::make_unique<GDIBrush>(brush);
    }
    
    // Create and cache
    HBRUSH brush = factory();
    if (brush) {
        brushCache_[key] = std::make_unique<GDIBrush>(factory());
    }
    
    return std::make_unique<GDIBrush>(brush);
}

GDIPenPtr GDIResourceManager::GetOrCreatePen(const std::string& key,
                                               std::function<HPEN()> factory) {
    auto it = penCache_.find(key);
    if (it != penCache_.end()) {
        // Create new instance from factory
        HPEN pen = factory();
        return std::make_unique<GDIPen>(pen);
    }
    
    // Create and cache
    HPEN pen = factory();
    if (pen) {
        penCache_[key] = std::make_unique<GDIPen>(factory());
    }
    
    return std::make_unique<GDIPen>(pen);
}

void GDIResourceManager::ClearCache() {
    fontCache_.clear();
    brushCache_.clear();
    penCache_.clear();
}

void GDIResourceManager::RemoveFont(const std::string& key) {
    fontCache_.erase(key);
}

void GDIResourceManager::RemoveBrush(const std::string& key) {
    brushCache_.erase(key);
}

void GDIResourceManager::RemovePen(const std::string& key) {
    penCache_.erase(key);
}

std::string GDIResourceManager::MakeFontKey(int height, int width, int weight,
                                            BOOL italic, const wchar_t* faceName) {
    std::ostringstream oss;
    oss << "font_" << height << "_" << width << "_" << weight 
        << "_" << (italic ? "i" : "n");
    if (faceName) {
        std::wstring wname(faceName);
        std::string name(wname.begin(), wname.end());
        oss << "_" << name;
    }
    return oss.str();
}

std::string GDIResourceManager::MakeBrushKey(COLORREF color) {
    std::ostringstream oss;
    oss << "brush_" << std::hex << std::setfill('0') << std::setw(8) << color;
    return oss.str();
}

std::string GDIResourceManager::MakePenKey(int style, int width, COLORREF color) {
    std::ostringstream oss;
    oss << "pen_" << style << "_" << width << "_" 
        << std::hex << std::setfill('0') << std::setw(8) << color;
    return oss.str();
}

