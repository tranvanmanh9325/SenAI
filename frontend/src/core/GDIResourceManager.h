#pragma once

#include <windows.h>
#include <memory>
#include <unordered_map>
#include <string>
#include <functional>

/**
 * GDIResourceManager - RAII-based resource manager for GDI objects
 * 
 * Provides automatic cleanup and caching for fonts, brushes, and pens.
 * Uses smart pointers to ensure proper resource management.
 */

// Forward declarations
class GDIFont;
class GDIBrush;
class GDIPen;

// Smart pointer types
using GDIFontPtr = std::unique_ptr<GDIFont>;
using GDIBrushPtr = std::unique_ptr<GDIBrush>;
using GDIPenPtr = std::unique_ptr<GDIPen>;

/**
 * GDIFont - RAII wrapper for HFONT
 */
class GDIFont {
public:
    GDIFont(HFONT font) : font_(font) {}
    ~GDIFont() {
        if (font_) {
            DeleteObject(font_);
        }
    }
    
    // Non-copyable
    GDIFont(const GDIFont&) = delete;
    GDIFont& operator=(const GDIFont&) = delete;
    
    // Movable
    GDIFont(GDIFont&& other) noexcept : font_(other.font_) {
        other.font_ = nullptr;
    }
    GDIFont& operator=(GDIFont&& other) noexcept {
        if (this != &other) {
            if (font_) DeleteObject(font_);
            font_ = other.font_;
            other.font_ = nullptr;
        }
        return *this;
    }
    
    HFONT Get() const { return font_; }
    operator HFONT() const { return font_; }
    
private:
    HFONT font_;
};

/**
 * GDIBrush - RAII wrapper for HBRUSH
 */
class GDIBrush {
public:
    GDIBrush(HBRUSH brush) : brush_(brush) {}
    ~GDIBrush() {
        if (brush_) {
            DeleteObject(brush_);
        }
    }
    
    // Non-copyable
    GDIBrush(const GDIBrush&) = delete;
    GDIBrush& operator=(const GDIBrush&) = delete;
    
    // Movable
    GDIBrush(GDIBrush&& other) noexcept : brush_(other.brush_) {
        other.brush_ = nullptr;
    }
    GDIBrush& operator=(GDIBrush&& other) noexcept {
        if (this != &other) {
            if (brush_) DeleteObject(brush_);
            brush_ = other.brush_;
            other.brush_ = nullptr;
        }
        return *this;
    }
    
    HBRUSH Get() const { return brush_; }
    operator HBRUSH() const { return brush_; }
    
private:
    HBRUSH brush_;
};

/**
 * GDIPen - RAII wrapper for HPEN
 */
class GDIPen {
public:
    GDIPen(HPEN pen) : pen_(pen) {}
    ~GDIPen() {
        if (pen_) {
            DeleteObject(pen_);
        }
    }
    
    // Non-copyable
    GDIPen(const GDIPen&) = delete;
    GDIPen& operator=(const GDIPen&) = delete;
    
    // Movable
    GDIPen(GDIPen&& other) noexcept : pen_(other.pen_) {
        other.pen_ = nullptr;
    }
    GDIPen& operator=(GDIPen&& other) noexcept {
        if (this != &other) {
            if (pen_) DeleteObject(pen_);
            pen_ = other.pen_;
            other.pen_ = nullptr;
        }
        return *this;
    }
    
    HPEN Get() const { return pen_; }
    operator HPEN() const { return pen_; }
    
private:
    HPEN pen_;
};

/**
 * GDIResourceManager - Centralized resource manager with caching
 */
class GDIResourceManager {
public:
    GDIResourceManager() = default;
    ~GDIResourceManager() {
        ClearCache();
    }
    
    // Non-copyable
    GDIResourceManager(const GDIResourceManager&) = delete;
    GDIResourceManager& operator=(const GDIResourceManager&) = delete;
    
    // Movable
    GDIResourceManager(GDIResourceManager&&) = default;
    GDIResourceManager& operator=(GDIResourceManager&&) = default;
    
    /**
     * Create a font with caching
     * @param height Font height (negative for logical units)
     * @param width Font width (0 for default)
     * @param escapement Text angle
     * @param orientation Font orientation
     * @param weight Font weight (FW_NORMAL, FW_BOLD, etc.)
     * @param italic Italic flag
     * @param underline Underline flag
     * @param strikeOut Strikeout flag
     * @param charset Character set
     * @param outputPrecision Output precision
     * @param clipPrecision Clipping precision
     * @param quality Output quality
     * @param pitchAndFamily Pitch and family
     * @param faceName Font face name
     * @return Smart pointer to font
     */
    GDIFontPtr CreateFont(
        int height, int width, int escapement, int orientation,
        int weight, BOOL italic, BOOL underline, BOOL strikeOut,
        DWORD charset, DWORD outputPrecision, DWORD clipPrecision,
        DWORD quality, DWORD pitchAndFamily, const wchar_t* faceName);
    
    /**
     * Create a solid brush with caching
     * @param color Brush color
     * @return Smart pointer to brush
     */
    GDIBrushPtr CreateSolidBrush(COLORREF color);
    
    /**
     * Create a pen with caching
     * @param style Pen style (PS_SOLID, etc.)
     * @param width Pen width
     * @param color Pen color
     * @return Smart pointer to pen
     */
    GDIPenPtr CreatePen(int style, int width, COLORREF color);
    
    /**
     * Get cached font or create new one
     * @param key Cache key
     * @param factory Function to create font if not cached
     * @return Smart pointer to font
     */
    GDIFontPtr GetOrCreateFont(const std::string& key, 
                                std::function<HFONT()> factory);
    
    /**
     * Get cached brush or create new one
     * @param key Cache key
     * @param factory Function to create brush if not cached
     * @return Smart pointer to brush
     */
    GDIBrushPtr GetOrCreateBrush(const std::string& key,
                                  std::function<HBRUSH()> factory);
    
    /**
     * Get cached pen or create new one
     * @param key Cache key
     * @param factory Function to create pen if not cached
     * @return Smart pointer to pen
     */
    GDIPenPtr GetOrCreatePen(const std::string& key,
                              std::function<HPEN()> factory);
    
    /**
     * Clear all cached resources
     */
    void ClearCache();
    
    /**
     * Remove specific cached resource
     */
    void RemoveFont(const std::string& key);
    void RemoveBrush(const std::string& key);
    void RemovePen(const std::string& key);
    
private:
    // Cache structures kept for future use if needed
    // Currently not used as GDI objects cannot be shared between DCs
    std::unordered_map<std::string, GDIFontPtr> fontCache_;
    std::unordered_map<std::string, GDIBrushPtr> brushCache_;
    std::unordered_map<std::string, GDIPenPtr> penCache_;
    
    // Helper functions for generating cache keys (kept for future use)
    std::string MakeFontKey(int height, int width, int weight, 
                           BOOL italic, const wchar_t* faceName);
    std::string MakeBrushKey(COLORREF color);
    std::string MakePenKey(int style, int width, COLORREF color);
};