#!/usr/bin/env python3
"""
Filter transcriptions to remove invalid/low-quality entries
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Set
import yaml
from tqdm import tqdm


class TranscriptionFilter:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.transcription_dir = Path(self.config['paths']['transcriptions'])
        self.input_file = self.transcription_dir / "transcriptions.jsonl"
        self.output_file = self.transcription_dir / "transcriptions_filtered.jsonl"
        self.rejected_file = self.transcription_dir / "rejected_transcriptions.jsonl"
        
        # Uzbek Latin alphabet characters (extended)
        self.uzbek_chars = set("abdefghijklmnopqrstuvwxyzABDEFGHIJKLMNOPQRSTUVWXYZ")
        
        # Common non-Uzbek patterns to detect
        self.cyrillic_pattern = re.compile(r'[А-Яа-яЁё]')
        self.arabic_pattern = re.compile(r'[\u0600-\u06FF]')
        self.chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
        
        # Load filter settings from config (with defaults)
        filter_config = self.config.get('filtering', {})
        self.min_length = filter_config.get('min_length', 3)
        self.max_length = filter_config.get('max_length', 1000)
        self.min_word_count = filter_config.get('min_word_count', 1)
        self.max_repetition_ratio = filter_config.get('max_repetition_ratio', 0.7)
        self.min_uzbek_char_ratio = filter_config.get('min_uzbek_char_ratio', 0.7)
    
    def is_valid_uzbek_text(self, text: str) -> bool:
        """Check if text appears to be valid Uzbek in Latin script"""
        if not text or not text.strip():
            return False
        
        text = text.strip()
        
        # Check length
        if len(text) < self.min_length or len(text) > self.max_length:
            return False
        
        # Check word count
        words = text.split()
        if len(words) < self.min_word_count:
            return False
        
        # Check for non-Uzbek scripts
        if self.cyrillic_pattern.search(text):
            return False  # Contains Cyrillic
        if self.arabic_pattern.search(text):
            return False  # Contains Arabic
        if self.chinese_pattern.search(text):
            return False  # Contains Chinese
        
        # Check ratio of Uzbek characters
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return False
        
        uzbek_letters = sum(1 for c in letters if c in self.uzbek_chars)
        uzbek_ratio = uzbek_letters / len(letters)
        
        if uzbek_ratio < self.min_uzbek_char_ratio:
            return False
        
        # Check for excessive repetition
        if self.has_excessive_repetition(words):
            return False
        
        return True
    
    def has_excessive_repetition(self, words: List[str]) -> bool:
        """Check if text has too many repeated words"""
        if len(words) < 3:
            return False
        
        word_counts = {}
        for word in words:
            word_lower = word.lower()
            word_counts[word_lower] = word_counts.get(word_lower, 0) + 1
        
        # Find most common word
        max_count = max(word_counts.values())
        repetition_ratio = max_count / len(words)
        
        return repetition_ratio > self.max_repetition_ratio
    
    def contains_error_markers(self, text: str) -> bool:
        """Check for common error markers in transcription"""
        text_lower = text.lower()
        
        error_markers = [
            '[unintelligible]',
            '[inaudible]',
            '[music]',
            '[noise]',
            '[silence]',
            '(unintelligible)',
            '(inaudible)',
            'error:',
            'failed',
            '***',
            '...',
            'n/a',
            'null',
            'undefined',
        ]
        
        return any(marker in text_lower for marker in error_markers)
    
    def has_valid_sentence_structure(self, text: str) -> bool:
        """Check if text has basic sentence structure"""
        # At least one space (multiple words)
        if ' ' not in text:
            if len(text) < 20:  # Single short word probably invalid
                return False
        
        # Check for basic punctuation presence (optional)
        # Uzbek text should have some punctuation in longer texts
        if len(text) > 100:
            has_punctuation = any(c in text for c in '.,!?;:-')
            if not has_punctuation:
                # Long text without punctuation is suspicious
                return True  # But we'll allow it for now
        
        return True
    
    def filter_jsonl(self, input_file: str = None, output_file: str = None,
                     rejected_file: str = None) -> Dict[str, int]:
        """
        Filter JSONL file and create filtered + rejected outputs
        
        Returns:
            Statistics dictionary
        """
        if input_file is None:
            input_file = self.input_file
        else:
            input_file = Path(input_file)
        
        if output_file is None:
            output_file = self.output_file
        else:
            output_file = Path(output_file)
        
        if rejected_file is None:
            rejected_file = self.rejected_file
        else:
            rejected_file = Path(rejected_file)
        
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        stats = {
            'total': 0,
            'valid': 0,
            'rejected': 0,
            'empty': 0,
            'too_short': 0,
            'too_long': 0,
            'wrong_script': 0,
            'excessive_repetition': 0,
            'error_markers': 0,
            'low_uzbek_ratio': 0,
        }
        
        with open(input_file, 'r', encoding='utf-8') as inf, \
             open(output_file, 'w', encoding='utf-8') as outf, \
             open(rejected_file, 'w', encoding='utf-8') as rejf:
            
            for line in tqdm(inf, desc="Filtering transcriptions"):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                stats['total'] += 1
                
                transcription = data.get('transcription', '').strip()
                
                # Empty check
                if not transcription:
                    stats['empty'] += 1
                    stats['rejected'] += 1
                    data['rejection_reason'] = 'empty'
                    rejf.write(json.dumps(data, ensure_ascii=False) + '\n')
                    continue
                
                # Determine rejection reason
                rejection_reasons = []
                
                # Length checks
                if len(transcription) < self.min_length:
                    stats['too_short'] += 1
                    rejection_reasons.append('too_short')
                
                if len(transcription) > self.max_length:
                    stats['too_long'] += 1
                    rejection_reasons.append('too_long')
                
                # Script checks
                if self.cyrillic_pattern.search(transcription):
                    stats['wrong_script'] += 1
                    rejection_reasons.append('contains_cyrillic')
                
                if self.arabic_pattern.search(transcription):
                    stats['wrong_script'] += 1
                    rejection_reasons.append('contains_arabic')
                
                if self.chinese_pattern.search(transcription):
                    stats['wrong_script'] += 1
                    rejection_reasons.append('contains_chinese')
                
                # Error markers
                if self.contains_error_markers(transcription):
                    stats['error_markers'] += 1
                    rejection_reasons.append('error_markers')
                
                # Uzbek character ratio
                letters = [c for c in transcription if c.isalpha()]
                if letters:
                    uzbek_letters = sum(1 for c in letters if c in self.uzbek_chars)
                    uzbek_ratio = uzbek_letters / len(letters)
                    if uzbek_ratio < self.min_uzbek_char_ratio:
                        stats['low_uzbek_ratio'] += 1
                        rejection_reasons.append('low_uzbek_ratio')
                
                # Repetition check
                words = transcription.split()
                if self.has_excessive_repetition(words):
                    stats['excessive_repetition'] += 1
                    rejection_reasons.append('excessive_repetition')
                
                # Final decision
                if rejection_reasons:
                    stats['rejected'] += 1
                    data['rejection_reason'] = ', '.join(rejection_reasons)
                    rejf.write(json.dumps(data, ensure_ascii=False) + '\n')
                else:
                    # Valid transcription
                    stats['valid'] += 1
                    outf.write(json.dumps(data, ensure_ascii=False) + '\n')
        
        return stats
    
    def filter_by_custom_rules(self, input_file: str, output_file: str,
                               custom_filter_func) -> int:
        """
        Filter using a custom function
        
        Args:
            input_file: Input JSONL path
            output_file: Output JSONL path
            custom_filter_func: Function that takes data dict and returns bool
        
        Returns:
            Number of kept entries
        """
        kept = 0
        
        with open(input_file, 'r', encoding='utf-8') as inf, \
             open(output_file, 'w', encoding='utf-8') as outf:
            
            for line in inf:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                if custom_filter_func(data):
                    outf.write(json.dumps(data, ensure_ascii=False) + '\n')
                    kept += 1
        
        return kept


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Filter transcriptions")
    parser.add_argument('--input', help='Input JSONL file (default from config)')
    parser.add_argument('--output', help='Output filtered JSONL file (default from config)')
    parser.add_argument('--rejected', help='Output rejected JSONL file (default from config)')
    parser.add_argument('--config', default='config/config.yaml', help='Config file path')
    
    # Filter settings
    parser.add_argument('--min-length', type=int, help='Minimum transcription length')
    parser.add_argument('--max-length', type=int, help='Maximum transcription length')
    parser.add_argument('--min-uzbek-ratio', type=float, help='Minimum Uzbek character ratio')
    parser.add_argument('--max-repetition', type=float, help='Maximum word repetition ratio')
    
    args = parser.parse_args()
    
    filterer = TranscriptionFilter(args.config)
    
    # Override settings if provided
    if args.min_length:
        filterer.min_length = args.min_length
    if args.max_length:
        filterer.max_length = args.max_length
    if args.min_uzbek_ratio:
        filterer.min_uzbek_char_ratio = args.min_uzbek_ratio
    if args.max_repetition:
        filterer.max_repetition_ratio = args.max_repetition
    
    # Filter
    stats = filterer.filter_jsonl(args.input, args.output, args.rejected)
    
    print("\n" + "="*60)
    print("FILTERING RESULTS")
    print("="*60)
    print(f"Total entries:           {stats['total']}")
    print(f"вњ… Valid transcriptions: {stats['valid']} ({stats['valid']/stats['total']*100:.1f}%)")
    print(f"вќЊ Rejected:             {stats['rejected']} ({stats['rejected']/stats['total']*100:.1f}%)")
    print()
    print("Rejection breakdown:")
    print(f"  - Empty:               {stats['empty']}")
    print(f"  - Too short:           {stats['too_short']}")
    print(f"  - Too long:            {stats['too_long']}")
    print(f"  - Wrong script:        {stats['wrong_script']}")
    print(f"  - Low Uzbek ratio:     {stats['low_uzbek_ratio']}")
    print(f"  - Excessive repetition:{stats['excessive_repetition']}")
    print(f"  - Error markers:       {stats['error_markers']}")
    print()
    print(f"рџ“„ Filtered output:  {filterer.output_file}")
    print(f"рџ—‘пёЏ  Rejected output: {filterer.rejected_file}")
    print("="*60)


if __name__ == "__main__":
    main()

