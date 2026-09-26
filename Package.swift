// swift-tools-version:5.9
// The Apple Vision OCR helper that scraper/pcblib/vision.py compiles with swiftc on first use.
// This manifest exists so `swift build` (and GitHub's CodeQL scan of Swift) can build it too.
import PackageDescription

let package = Package(
    name: "VisionOCR",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(name: "vision-ocr", path: "scraper/pcblib/vision_ocr"),
    ]
)
