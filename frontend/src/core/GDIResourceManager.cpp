#include "GDIResourceManager.h"
#include <sstream>
#include <iomanip>

GDIFontPtr GDIResourceManager::CreateFont(
    int height, int width, int escapement, int orientation,
    int weight, BOOL italic, BOOL underline, BOOL strikeOut,
    DWORD charset, DWORD outputPrecision, DWORD clipPrecision,
    DWORD quality, DWORD pitchAndFamily, const wchar_t* faceName) {
    
    // Create new font - GDI fonts cannot be shared between DCs,
    // so we create a new one each time and let smart pointer handle cleanup
    HFONT font = CreateFontW(height, width, escapement, orientation,
                            weight, italic, underline, strikeOut,
                            charset, outputPrecision, clipPrecision,
                            quality, pitchAndFamily, faceName);
    
    return std::make_unique<GDIFont>(font);
}

GDIBrushPtr GDIResourceManager::CreateSolidBrush(COLORREF color) {
    // Create new brush - let smart pointer handle cleanup
    HBRUSH brush = ::CreateSolidBrush(color);
    return std::make_unique<GDIBrush>(brush);
}

GDIPenPtr GDIResourceManager::CreatePen(int style, int width, COLORREF color) {
    // Create new pen - let smart pointer handle cleanup
    HPEN pen = ::CreatePen(style, width, color);
    return std::make_unique<GDIPen>(pen);
}

GDIFontPtr GDIResourceManager::GetOrCreateFont(const std::string& /*key*/,
                                                 std::function<HFONT()> factory) {
    // Simply create from factory - caching not needed as fonts can't be shared
    // Key parameter kept for API compatibility but not used
    HFONT font = factory();
    return std::make_unique<GDIFont>(font);
}

GDIBrushPtr GDIResourceManager::GetOrCreateBrush(const std::string& /*key*/,
                                                   std::function<HBRUSH()> factory) {
    // Simply create from factory
    // Key parameter kept for API compatibility but not used
    HBRUSH brush = factory();
    return std::make_unique<GDIBrush>(brush);
}

GDIPenPtr GDIResourceManager::GetOrCreatePen(const std::string& /*key*/,
                                               std::function<HPEN()> factory) {
    // Simply create from factory
    // Key parameter kept for API compatibility but not used
    HPEN pen = factory();
    return std::make_unique<GDIPen>(pen);
}

void GDIResourceManager::ClearCache() {
    // Clear cache (currently not used but kept for future use)
    fontCache_.clear();
    brushCache_.clear();
    penCache_.clear();
}

void GDIResourceManager::RemoveFont(const std::string& key) {
    // Remove from cache (currently not used but kept for future use)
    fontCache_.erase(key);
}

void GDIResourceManager::RemoveBrush(const std::string& key) {
    // Remove from cache (currently not used but kept for future use)
    brushCache_.erase(key);
}

void GDIResourceManager::RemovePen(const std::string& key) {
    // Remove from cache (currently not used but kept for future use)
    penCache_.erase(key);
}

std::string GDIResourceManager::MakeFontKey(int height, int width, int weight,
                                            BOOL italic, const wchar_t* faceName) {
    // Generate cache key for font (currently not used but kept for future use)
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
    // Generate cache key for brush (currently not used but kept for future use)
    std::ostringstream oss;
    oss << "brush_" << std::hex << std::setfill('0') << std::setw(8) << color;
    return oss.str();
}

std::string GDIResourceManager::MakePenKey(int style, int width, COLORREF color) {
    // Generate cache key for pen (currently not used but kept for future use)
    std::ostringstream oss;
    oss << "pen_" << style << "_" << width << "_" 
        << std::hex << std::setfill('0') << std::setw(8) << color;
    return oss.str();
}