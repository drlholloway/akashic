// Word boxes from Apple's Vision text recognizer, for pcblib/vision.py.
// Usage: vision-ocr <image>
// One line per word: line index, x0, y0, x1, y1 (0..1, origin top left), confidence, text.
import AppKit
import Vision

guard CommandLine.arguments.count == 2,
      let image = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("cannot read image\n".data(using: .utf8)!)
    exit(1)
}
// Vision loses small type in a tall image (a page-length column strip), so an image taller
// than a band is read in overlapping horizontal bands; a word is kept from the band where
// its centre lies outside the overlap, so a line is reported once.
let height = Double(cg.height)
let band = 1100.0, overlap = 150.0
var starts: [Double] = [0]
while starts.last! + band < height { starts.append(starts.last! + band - overlap) }
var out = ""
var lineIndex = 0
for (n, top) in starts.enumerated() {
    let bottom = min(height, top + band)
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["en-US"]
    request.usesLanguageCorrection = false  // part values are not words
    request.minimumTextHeight = Float(0.004 * height / (bottom - top))
    // regionOfInterest is normalized with its origin at the bottom left
    request.regionOfInterest = CGRect(x: 0, y: (height - bottom) / height, width: 1, height: (bottom - top) / height)
    do {
        try VNImageRequestHandler(cgImage: cg).perform([request])
    } catch {
        FileHandle.standardError.write("\(error)\n".data(using: .utf8)!)
        exit(1)
    }
    let keepFrom = n == 0 ? 0 : top + overlap / 2
    let keepTo = n == starts.count - 1 ? height : bottom - overlap / 2
    for observation in request.results ?? [] {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let text = candidate.string
        var lineOut = ""
        var start = text.startIndex
        while start < text.endIndex {
            guard let wordStart = text[start...].firstIndex(where: { !$0.isWhitespace }) else { break }
            let wordEnd = text[wordStart...].firstIndex(where: { $0.isWhitespace }) ?? text.endIndex
            let range = wordStart..<wordEnd
            // boxes come back relative to the region of interest
            let r = (try? candidate.boundingBox(for: range))?.boundingBox ?? observation.boundingBox
            let y0 = top + (1 - r.maxY) * (bottom - top), y1 = top + (1 - r.minY) * (bottom - top)
            let centre = (y0 + y1) / 2
            if centre >= keepFrom && centre < keepTo {
                lineOut += String(format: "%d\t%.5f\t%.5f\t%.5f\t%.5f\t%.2f\t", lineIndex, r.minX, y0 / height, r.maxX, y1 / height, candidate.confidence)
                lineOut += String(text[range]) + "\n"
            }
            start = wordEnd
        }
        if !lineOut.isEmpty {
            out += lineOut
            lineIndex += 1
        }
    }
}
FileHandle.standardOutput.write(out.data(using: .utf8)!)
