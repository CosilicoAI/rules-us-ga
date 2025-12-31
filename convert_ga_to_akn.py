#!/usr/bin/env python3
"""Convert Georgia OCGA XML (Internet Archive format) to Akoma Ntoso XML.

This script processes the Georgia statute XML files from the Internet Archive
(archive.org) OCGA collection and converts them to Akoma Ntoso format.

Source format: Custom XML with HTML-escaped content in <Content> tags
Target format: OASIS Akoma Ntoso 3.0

Usage:
    python convert_ga_to_akn.py

Output:
    Creates AKN XML files in /tmp/rules-us-ga-akn/
"""

import html
import re
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

# Paths
SOURCE_DIR = Path("/Users/maxghenis/CosilicoAI/arch/data/statutes/us-ga/xml.2018")
OUTPUT_DIR = Path("/tmp/rules-us-ga-akn")

# Akoma Ntoso namespace
AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"


def clean_html_content(html_content: str) -> str:
    """Extract plain text from HTML-escaped content."""
    # Unescape HTML entities
    text = html.unescape(html_content)

    # Remove HTML tags
    text = re.sub(r"<BR\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<P>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</P>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<STRONG>|</STRONG>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<B>|</B>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<FONT[^>]*>|</FONT>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)  # Remove remaining tags

    # Clean up whitespace
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = text.strip()

    return text


def extract_section_number(caption: str) -> str:
    """Extract section number from caption like '48-1-2'."""
    match = re.search(r"(\d+-\d+-\d+(?:\.\d+)?)", caption)
    if match:
        return match.group(1)
    return caption.replace(" ", "-").replace(".", "-")


def create_eid(section_num: str) -> str:
    """Create eId from section number (e.g., '48-1-2' -> 'sec_48-1-2')."""
    return f"sec_{section_num}"


def parse_subsections(text: str) -> list[dict]:
    """Parse hierarchical subsections from text.

    Georgia statutes typically use:
    - (a), (b), (c) for primary divisions
    - (1), (2), (3) for secondary divisions
    - (A), (B), (C) for tertiary divisions
    """
    subsections = []

    # Split by top-level subsections (a), (b), etc.
    parts = re.split(r"(?=\([a-z]\)\s)", text)

    for part in parts[1:]:  # Skip content before first (a)
        match = re.match(r"\(([a-z])\)\s*", part)
        if not match:
            continue

        identifier = match.group(1)
        content = part[match.end():]

        # Get text before any numeric subsection
        numeric_match = re.search(r"\(\d+\)", content)
        if numeric_match:
            direct_text = content[: numeric_match.start()].strip()
            remaining = content[numeric_match.start():]
        else:
            direct_text = content.strip()
            remaining = ""

        # Parse numeric children
        children = []
        if remaining:
            num_parts = re.split(r"(?=\(\d+\)\s)", remaining)
            for num_part in num_parts[1:]:
                num_match = re.match(r"\((\d+)\)\s*", num_part)
                if num_match:
                    num_id = num_match.group(1)
                    num_text = num_part[num_match.end():].strip()
                    # Stop at next subsection marker
                    next_marker = re.search(r"\([a-z]\)|\(\d+\)", num_text)
                    if next_marker:
                        num_text = num_text[: next_marker.start()].strip()
                    children.append({
                        "identifier": num_id,
                        "text": num_text[:2000],  # Limit text length
                        "children": [],
                    })

        # Stop at next subsection
        next_sub = re.search(r"\([a-z]\)", direct_text)
        if next_sub:
            direct_text = direct_text[: next_sub.start()].strip()

        subsections.append({
            "identifier": identifier,
            "text": direct_text[:2000],
            "children": children,
        })

    return subsections


def create_akn_document(title_num: int, sections: list[dict]) -> ET.Element:
    """Create an Akoma Ntoso document for a title."""
    # Register default namespace
    ET.register_namespace("", AKN_NS)

    # Root element
    root = ET.Element(f"{{{AKN_NS}}}akomaNtoso")

    # Act container
    act = ET.SubElement(root, f"{{{AKN_NS}}}act")

    # Meta section
    meta = ET.SubElement(act, f"{{{AKN_NS}}}meta")

    # Identification
    ident = ET.SubElement(meta, f"{{{AKN_NS}}}identification")
    ident.set("source", "#cosilico")

    # FRBRWork
    work = ET.SubElement(ident, f"{{{AKN_NS}}}FRBRWork")
    work_this = ET.SubElement(work, f"{{{AKN_NS}}}FRBRthis")
    work_this.set("value", f"/akn/us-ga/act/ocga/title-{title_num}")
    work_uri = ET.SubElement(work, f"{{{AKN_NS}}}FRBRuri")
    work_uri.set("value", f"/akn/us-ga/act/ocga/title-{title_num}")
    work_date = ET.SubElement(work, f"{{{AKN_NS}}}FRBRdate")
    work_date.set("date", "2018-12-01")
    work_date.set("name", "publication")
    work_author = ET.SubElement(work, f"{{{AKN_NS}}}FRBRauthor")
    work_author.set("href", "#ga-legislature")
    work_country = ET.SubElement(work, f"{{{AKN_NS}}}FRBRcountry")
    work_country.set("value", "us-ga")
    work_number = ET.SubElement(work, f"{{{AKN_NS}}}FRBRnumber")
    work_number.set("value", str(title_num))

    # FRBRExpression
    expr = ET.SubElement(ident, f"{{{AKN_NS}}}FRBRExpression")
    expr_this = ET.SubElement(expr, f"{{{AKN_NS}}}FRBRthis")
    expr_this.set("value", f"/akn/us-ga/act/ocga/title-{title_num}/eng@2018-12-01")
    expr_uri = ET.SubElement(expr, f"{{{AKN_NS}}}FRBRuri")
    expr_uri.set("value", f"/akn/us-ga/act/ocga/title-{title_num}/eng@2018-12-01")
    expr_date = ET.SubElement(expr, f"{{{AKN_NS}}}FRBRdate")
    expr_date.set("date", "2018-12-01")
    expr_date.set("name", "publication")
    expr_author = ET.SubElement(expr, f"{{{AKN_NS}}}FRBRauthor")
    expr_author.set("href", "#cosilico")
    expr_lang = ET.SubElement(expr, f"{{{AKN_NS}}}FRBRlanguage")
    expr_lang.set("language", "eng")

    # FRBRManifestation
    manif = ET.SubElement(ident, f"{{{AKN_NS}}}FRBRManifestation")
    manif_this = ET.SubElement(manif, f"{{{AKN_NS}}}FRBRthis")
    manif_this.set("value", f"/akn/us-ga/act/ocga/title-{title_num}/eng@2018-12-01/main.xml")
    manif_uri = ET.SubElement(manif, f"{{{AKN_NS}}}FRBRuri")
    manif_uri.set("value", f"/akn/us-ga/act/ocga/title-{title_num}/eng@2018-12-01/main.xml")
    manif_date = ET.SubElement(manif, f"{{{AKN_NS}}}FRBRdate")
    manif_date.set("date", date.today().isoformat())
    manif_date.set("name", "generation")
    manif_author = ET.SubElement(manif, f"{{{AKN_NS}}}FRBRauthor")
    manif_author.set("href", "#cosilico")

    # Publication
    pub = ET.SubElement(meta, f"{{{AKN_NS}}}publication")
    pub.set("date", "2018-12-01")
    pub.set("name", "Official Code of Georgia Annotated")
    pub.set("showAs", "OCGA")

    # References section for TLC entries
    refs = ET.SubElement(meta, f"{{{AKN_NS}}}references")

    org_ga = ET.SubElement(refs, f"{{{AKN_NS}}}TLCOrganization")
    org_ga.set("eId", "ga-legislature")
    org_ga.set("href", "/ontology/organization/us-ga/legislature")
    org_ga.set("showAs", "Georgia General Assembly")

    org_cos = ET.SubElement(refs, f"{{{AKN_NS}}}TLCOrganization")
    org_cos.set("eId", "cosilico")
    org_cos.set("href", "https://cosilico.ai")
    org_cos.set("showAs", "Cosilico")

    # Body with sections
    body = ET.SubElement(act, f"{{{AKN_NS}}}body")

    # Group sections by chapter
    chapters: dict[str, list[dict]] = {}
    for section in sections:
        chapter = section.get("chapter", "0")
        if chapter not in chapters:
            chapters[chapter] = []
        chapters[chapter].append(section)

    for chapter_num, chapter_sections in sorted(chapters.items()):
        if not chapter_num:
            continue

        # Create chapter element
        chapter_elem = ET.SubElement(body, f"{{{AKN_NS}}}chapter")
        chapter_elem.set("eId", f"chp_{title_num}-{chapter_num}")

        chapter_num_elem = ET.SubElement(chapter_elem, f"{{{AKN_NS}}}num")
        chapter_num_elem.text = f"Chapter {chapter_num}"

        chapter_title = chapter_sections[0].get("chapter_title", "")
        if chapter_title:
            chapter_heading = ET.SubElement(chapter_elem, f"{{{AKN_NS}}}heading")
            chapter_heading.text = chapter_title

        for section in chapter_sections:
            add_section_element(chapter_elem, section)

    return root


def add_section_element(parent: ET.Element, section: dict) -> None:
    """Add a section element with subsections."""
    section_num = section["section_number"]
    eid = create_eid(section_num)

    sec_elem = ET.SubElement(parent, f"{{{AKN_NS}}}section")
    sec_elem.set("eId", eid)

    # Number
    num_elem = ET.SubElement(sec_elem, f"{{{AKN_NS}}}num")
    num_elem.text = f"{section_num}"

    # Heading
    if section.get("title"):
        heading_elem = ET.SubElement(sec_elem, f"{{{AKN_NS}}}heading")
        heading_elem.text = section["title"]

    # Content
    text = section.get("text", "")
    subsections = section.get("subsections", [])

    if subsections:
        # Add intro text if present
        intro_match = re.match(r"^(.+?)(?=\([a-z]\))", text, re.DOTALL)
        if intro_match:
            intro_elem = ET.SubElement(sec_elem, f"{{{AKN_NS}}}intro")
            intro_p = ET.SubElement(intro_elem, f"{{{AKN_NS}}}p")
            intro_p.text = intro_match.group(1).strip()[:500]

        # Add subsections
        for sub in subsections:
            add_subsection_element(sec_elem, sub, section_num)
    else:
        # Just content
        content_elem = ET.SubElement(sec_elem, f"{{{AKN_NS}}}content")
        p_elem = ET.SubElement(content_elem, f"{{{AKN_NS}}}p")
        p_elem.text = text[:5000]  # Limit text length

    # History note
    if section.get("history"):
        notes_elem = ET.SubElement(sec_elem, f"{{{AKN_NS}}}notes")
        note_elem = ET.SubElement(notes_elem, f"{{{AKN_NS}}}note")
        note_elem.set("type", "history")
        note_p = ET.SubElement(note_elem, f"{{{AKN_NS}}}p")
        note_p.text = section["history"][:1000]


def add_subsection_element(parent: ET.Element, sub: dict, section_num: str) -> None:
    """Add a subsection element with nested children."""
    identifier = sub["identifier"]
    eid = f"sec_{section_num}__subsec_{identifier}"

    subsec_elem = ET.SubElement(parent, f"{{{AKN_NS}}}subsection")
    subsec_elem.set("eId", eid)

    # Number
    num_elem = ET.SubElement(subsec_elem, f"{{{AKN_NS}}}num")
    num_elem.text = f"({identifier})"

    # Content
    content_elem = ET.SubElement(subsec_elem, f"{{{AKN_NS}}}content")
    p_elem = ET.SubElement(content_elem, f"{{{AKN_NS}}}p")
    p_elem.text = sub["text"]

    # Add children (paragraphs)
    for child in sub.get("children", []):
        child_id = child["identifier"]
        child_eid = f"{eid}__para_{child_id}"

        para_elem = ET.SubElement(subsec_elem, f"{{{AKN_NS}}}paragraph")
        para_elem.set("eId", child_eid)

        para_num = ET.SubElement(para_elem, f"{{{AKN_NS}}}num")
        para_num.text = f"({child_id})"

        para_content = ET.SubElement(para_elem, f"{{{AKN_NS}}}content")
        para_p = ET.SubElement(para_content, f"{{{AKN_NS}}}p")
        para_p.text = child["text"]


def parse_source_xml(source_file: Path) -> list[dict]:
    """Parse the Internet Archive GA XML format."""
    tree = ET.parse(source_file)
    root = tree.getroot()

    sections = []

    # Find all Index elements at level 3 or 4 (sections)
    for index in root.iter("Index"):
        level = index.get("Level", "")
        if level not in ("3", "4"):
            continue

        caption = index.find("Caption")
        if caption is None or not caption.text:
            continue

        caption_text = caption.text.strip()

        # Skip non-section entries
        if not re.search(r"\d+-\d+-\d+", caption_text):
            continue

        section_number = extract_section_number(caption_text)

        # Get description (title)
        desc_elem = index.find("Description")
        title = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ""

        # Get content
        content_elem = index.find("Content")
        content = ""
        if content_elem is not None and content_elem.text:
            content = clean_html_content(content_elem.text)

        # Get history
        history_elem = index.find("RevisionHistory")
        history = history_elem.text.strip() if history_elem is not None and history_elem.text else ""

        # Parse chapter from section number
        parts = section_number.split("-")
        chapter = parts[1] if len(parts) > 1 else ""

        # Parse subsections
        subsections = parse_subsections(content)

        sections.append({
            "section_number": section_number,
            "title": title,
            "text": content,
            "history": history,
            "chapter": chapter,
            "subsections": subsections,
        })

    return sections


def pretty_print_xml(elem: ET.Element) -> str:
    """Convert element to pretty-printed XML string."""
    from xml.dom import minidom

    rough_string = ET.tostring(elem, encoding="unicode")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def main():
    """Main conversion function."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Process each title XML file
    xml_files = sorted(SOURCE_DIR.glob("gov.ga.ocga.2018.title.*.xml"))

    print(f"Found {len(xml_files)} Georgia title files in {SOURCE_DIR}")

    stats = {
        "titles_processed": 0,
        "sections_converted": 0,
        "files_written": 0,
    }

    for source_file in xml_files:
        # Extract title number from filename
        match = re.search(r"title\.(\d+)\.xml$", source_file.name)
        if not match:
            print(f"Skipping {source_file.name} - could not extract title number")
            continue

        title_num = int(match.group(1))
        print(f"\nProcessing Title {title_num}...")

        try:
            # Parse source
            sections = parse_source_xml(source_file)

            if not sections:
                print(f"  No sections found in {source_file.name}")
                continue

            print(f"  Found {len(sections)} sections")

            # Create AKN document
            akn_doc = create_akn_document(title_num, sections)

            # Write output
            output_file = OUTPUT_DIR / f"us-ga-title-{title_num:02d}.akn.xml"
            xml_str = pretty_print_xml(akn_doc)

            # Add XML declaration
            if not xml_str.startswith("<?xml"):
                xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

            output_file.write_text(xml_str, encoding="utf-8")
            print(f"  Wrote {output_file.name} ({len(sections)} sections)")

            stats["titles_processed"] += 1
            stats["sections_converted"] += len(sections)
            stats["files_written"] += 1

        except Exception as e:
            print(f"  ERROR processing {source_file.name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("Conversion Summary")
    print("=" * 60)
    print(f"Titles processed: {stats['titles_processed']}")
    print(f"Sections converted: {stats['sections_converted']}")
    print(f"Files written: {stats['files_written']}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
