#
# Copyright (c) 2025, Speechmatics / Cantab Research Ltd
#

from __future__ import annotations

import datetime
import re
import unicodedata
from typing import Optional

from ._models import AnnotationFlags
from ._models import AnnotationResult
from ._models import ClientSessionInfo
from ._models import SpeakerSegment
from ._models import SpeakerSegmentView
from ._models import SpeechFragment


class FragmentUtils:
    """Set of utility functions for working with SpeechFragment and SpeakerSegment objects."""

    @staticmethod
    def format_segment_text(
        session: ClientSessionInfo,
        segment: SpeakerSegment,
        format: str = "{text}",
        words_only: bool = False,
        include_partials: bool = True,
    ) -> str:
        """Format a segment's text based on the language pack info.

        Args:
            session: ClientSessionInfo object.
            segment: SpeakerSegment object.
            format: Format string.
            words_only: Whether to include only word fragments.
            include_partials: Whether to include partial fragments.

        Returns:
            str: The formatted text.
        """

        # Cumulative contents
        content = ""

        # Select fragments to include
        if words_only:
            fragments = [frag for frag in segment.fragments if frag.type_ == "word"]
        else:
            fragments = segment.fragments

        # Filter out partials if requested
        if not include_partials:
            fragments = [frag for frag in fragments if frag.is_final]

        # Assemble the text
        previous_frag: Optional[SpeechFragment] = None
        for frag in fragments:
            if not previous_frag:
                content = frag.content
            elif frag.attaches_to == "previous" or previous_frag.attaches_to == "next":
                content += frag.content
            else:
                content += session.language_pack_info.word_delimiter + frag.content
            previous_frag = frag

        # Return the formatted text
        return format.format(
            **{
                "speaker_id": segment.speaker_id,
                "text": content,
                "content": content,
                "ts": segment.timestamp,
                "lang": segment.language,
                "start_time": fragments[0].start_time if fragments else 0,
                "end_time": fragments[-1].end_time if fragments else 0,
                "annotation": segment.annotation or [],
            }
        )

    @staticmethod
    def segment_list_from_fragments(
        session: ClientSessionInfo,
        fragments: list[SpeechFragment],
        focus_speakers: Optional[list[str]] = None,
        annotate_segments: bool = True,
    ) -> list[SpeakerSegment]:
        """Create SpeakerSegment objects from a list of SpeechFragment objects.

        Args:
            session: ClientSessionInfo object.
            fragments: List of SpeechFragment objects.
            focus_speakers: List of speakers to focus on or None.
            annotate_segments: Whether to annotate segments.

        Returns:
            List of SpeakerSegment objects.
        """

        # Speaker groups
        current_speaker: Optional[str] = None
        speaker_groups: list[list[SpeechFragment]] = [[]]

        # Group by speakers
        for frag in fragments:
            if frag.speaker != current_speaker:
                current_speaker = frag.speaker
                if speaker_groups[-1]:
                    speaker_groups.append([])
            speaker_groups[-1].append(frag)

        # Create SpeakerFragments objects
        segments: list[SpeakerSegment] = []
        for group in speaker_groups:
            # Skip if the group is empty
            if not group:
                continue

            # Split group into sub-groups by end-of-sentence markers (finals only)
            if session.config.speech_segment_config.emit_sentences:
                subgroup: list[SpeechFragment] = []
                subgroups: list[list[SpeechFragment]] = []
                for frag in group:
                    subgroup.append(frag)
                    if frag.is_eos and frag.is_final:
                        subgroups.append(subgroup)
                        subgroup = []
                if subgroup:
                    subgroups.append(subgroup)
            else:
                subgroups = [group]

            # Process each of the sub-groups
            for fragments_subset in subgroups:
                segment = FragmentUtils.segment_from_fragments(
                    session=session,
                    fragments=fragments_subset,
                    focus_speakers=focus_speakers,
                    annotate=annotate_segments,
                )
                if segment:
                    FragmentUtils.update_segment_text(session=session, segment=segment)
                    segments.append(segment)

        # Return the grouped SpeakerFragments objects
        return segments

    @staticmethod
    def update_segment_text(session: ClientSessionInfo, segment: SpeakerSegment) -> None:
        """Update the text of a segment based on the language pack info.

        Args:
            session: ClientSessionInfo object.
            segment: SpeakerSegment object.
        """
        segment.text = FragmentUtils.format_segment_text(
            session=session, segment=segment, include_partials=session.config.include_partials
        )

    @staticmethod
    def segment_from_fragments(
        session: ClientSessionInfo,
        fragments: list[SpeechFragment],
        focus_speakers: Optional[list[str]] = None,
        annotate: bool = True,
    ) -> Optional[SpeakerSegment]:
        """Take a group of fragments and piece together into SpeakerSegment.

        Each fragment for a given speaker is assembled into a string,
        taking into consideration whether words are attached to the
        previous or next word (notably punctuation). This ensures that
        the text does not have extra spaces. This will also check for
        any straggling punctuation from earlier utterances that should
        be removed.

        Args:
            session: ClientSessionInfo object.
            fragments: List of SpeechFragment objects.
            focus_speakers: List of speakers to focus on.
            annotate: Whether to annotate the segment.

        Returns:
            The SpeakerSegment object for the group, or None if no valid fragments.
        """
        # Check for starting fragments that are attached to previous
        if fragments and fragments[0].attaches_to == "previous":
            fragments = fragments[1:]

        # Check for trailing fragments that are attached to next
        if fragments and fragments[-1].attaches_to == "next":
            fragments = fragments[:-1]

        # Check there are results
        if not fragments:
            return None

        # Get the timing extremes
        start_time = min(frag.start_time for frag in fragments)

        # Timestamp
        ts = (session.base_time + datetime.timedelta(seconds=start_time)).isoformat(timespec="milliseconds")

        # Determine if the speaker is considered active
        is_active = True
        if focus_speakers:
            is_active = fragments[0].speaker in focus_speakers

        # New SpeakerSegment
        segment = SpeakerSegment(
            speaker_id=fragments[0].speaker,
            timestamp=ts,
            language=fragments[0].language,
            fragments=fragments,
            is_active=is_active,
        )

        # Annotate
        if annotate:
            segment.annotation = FragmentUtils._annotate_segment(segment)

        # Return the SpeakerSegment object
        return segment

    @staticmethod
    def _annotate_segment(segment: SpeakerSegment) -> AnnotationResult:
        """Annotate the segment with any additional information.

        Args:
            segment: SpeakerSegment object.

        Returns:
            AnnotationResult: The annotation result.
        """
        # Annotation result
        result = AnnotationResult()

        # References
        segment_length: int = len(segment.fragments)
        first_fragment: SpeechFragment = segment.fragments[0]
        last_fragment: SpeechFragment = segment.fragments[-1]
        penultimate_fragment: Optional[SpeechFragment] = segment.fragments[-2] if segment_length > 1 else None

        # Count of words
        words = [frag for frag in segment.fragments if frag.type_ == "word"]
        word_count = len(words)
        if word_count == 0:
            result.add(AnnotationFlags.NO_TEXT)

        # Only punctuation
        if all(frag.is_punctuation for frag in segment.fragments):
            result.add(AnnotationFlags.ONLY_PUNCTUATION)

        # Partials and finals
        if any(not frag.is_final for frag in segment.fragments):
            result.add(AnnotationFlags.HAS_PARTIAL)

        # Finals
        if any(frag.is_final for frag in segment.fragments):
            result.add(AnnotationFlags.HAS_FINAL)
        if first_fragment.is_final:
            result.add(AnnotationFlags.STARTS_WITH_FINAL)
        if last_fragment.is_final:
            result.add(AnnotationFlags.ENDS_WITH_FINAL)

        # End of sentence
        if last_fragment.is_eos:
            result.add(AnnotationFlags.ENDS_WITH_EOS)

        # Punctuation
        if last_fragment.is_punctuation:
            result.add(AnnotationFlags.ENDS_WITH_PUNCTUATION)

        # Disfluency
        if any(frag.is_disfluency for frag in segment.fragments):
            result.add(AnnotationFlags.HAS_DISFLUENCY)
        if first_fragment.is_disfluency:
            result.add(AnnotationFlags.STARTS_WITH_DISFLUENCY)
        if last_fragment.is_disfluency:
            result.add(AnnotationFlags.ENDS_WITH_DISFLUENCY)
        if (
            penultimate_fragment
            and result.any(AnnotationFlags.ENDS_WITH_EOS, AnnotationFlags.ENDS_WITH_PUNCTUATION)
            and penultimate_fragment.is_disfluency
        ):
            result.add(AnnotationFlags.ENDS_WITH_DISFLUENCY)

        # Rate of speech
        if len(words) > 1:
            # Calculate the approximate words-per-minute (for last few words)
            recent_words = words[-10:]
            word_time_span = recent_words[-1].end_time - recent_words[0].start_time
            wpm = (len(recent_words) / word_time_span) * 60

            # Categorize the speaker
            if wpm < 80:
                result.add(AnnotationFlags.VERY_SLOW_SPEAKER)
            elif wpm < 110:
                result.add(AnnotationFlags.SLOW_SPEAKER)
            elif wpm > 250:
                result.add(AnnotationFlags.FAST_SPEAKER)

        # Return the annotation result
        return result

    @staticmethod
    def compare_views(
        session: ClientSessionInfo, view1: SpeakerSegmentView, view2: Optional[SpeakerSegmentView]
    ) -> AnnotationResult:
        """Compare two SpeakerSegmentView objects and return the differences.

        View 1 (new) is compared to view 2 (old).

        Args:
            session: ClientSessionInfo object.
            view1: The first SpeakerSegmentView object to compare.
            view2: The second SpeakerSegmentView object to compare to or None.

        Returns:
            AnnotationResult: The annotation result.
        """
        # Result
        result = AnnotationResult()

        # Flag to include partials
        include_partials = session.config.include_partials

        # If we have a previous view, compare it
        if view2 and view2.segment_count > 0:
            # Compare full string
            view1_full_str: str = view1.format_view_text(include_partials=include_partials)
            view2_full_str: str = view2.format_view_text(include_partials=include_partials)
            if view1_full_str != view2_full_str:
                result.add(AnnotationFlags.UPDATED_FULL)
            if view1_full_str.lower() != view2_full_str.lower():
                result.add(AnnotationFlags.UPDATED_FULL_LCASE)

            # Stripped string (without punctuation)
            view1_stripped_str: str = view1.format_view_text(include_partials=include_partials, words_only=True)
            view2_stripped_str: str = view2.format_view_text(include_partials=include_partials, words_only=True)
            if view1_stripped_str != view2_stripped_str:
                result.add(AnnotationFlags.UPDATED_STRIPPED)
            if view1_stripped_str.lower() != view2_stripped_str.lower():
                result.add(AnnotationFlags.UPDATED_STRIPPED_LCASE)

            # Word timings
            view1_timings_str: str = view1.format_view_text(
                format="|{start_time}-{end_time}|", words_only=True, include_partials=include_partials
            )
            view2_timings_str: str = view2.format_view_text(
                format="|{start_time}-{end_time}|", words_only=True, include_partials=include_partials
            )
            if view1_timings_str != view2_timings_str:
                result.add(AnnotationFlags.UPDATED_WORD_TIMINGS)

            # Annotations
            view1_annotation_str: str = view1.format_view_text(format="|{annotation}|")
            view2_annotation_str: str = view2.format_view_text(format="|{annotation}|")
            if set(view1_annotation_str) != set(view2_annotation_str):
                result.add(AnnotationFlags.UPDATED_ANNOTATIONS)

            # Partials, finals and speakers
            if view1.final_count != view2.final_count:
                result.add(AnnotationFlags.UPDATED_FINALS)
            if view1.partial_count != view2.partial_count:
                result.add(AnnotationFlags.UPDATED_PARTIALS)

        # Assume this is new
        elif view1.segment_count > 0:
            result.add(AnnotationFlags.NEW)

        # Finalized (last segment only has finals)
        if view1.segment_count > 0 and view1.partial_count == 0:
            result.add(AnnotationFlags.FINALIZED)

        # Return the result
        return result

    @staticmethod
    def find_segment_pauses(session: ClientSessionInfo, view: SpeakerSegmentView) -> None:
        """Find gaps in the segments.

        LLMs may find knowledge of when someone pauses between words of use when constructing
        their reply. This utility adds in pause markers to the segments which can then be used
        during the text formatting of the segment.

        Args:
            session: ClientSessionInfo object.
            view: The SpeakerSegmentView object to process.
        """

        # Find gaps in the view
        for segment in view.segments:
            # Strip out existing pauses
            words = [f for f in segment.fragments if f.type_ != "pause"]

            # Find gaps between the end of one word and the start of the next
            for i in range(len(words) - 1):
                word = words[i]
                next_word = words[i + 1]
                gap_start = word.end_time
                gap_end = next_word.start_time
                if gap_end - gap_start > 0.1:
                    segment.fragments.append(
                        SpeechFragment(
                            idx=word.idx + 1,
                            type_="pause",
                            start_time=gap_start,
                            end_time=gap_end,
                            is_final=word.is_final,
                            content=session.config.speech_segment_config.pause_mark or "...",
                        )
                    )

            # Resort the fragments
            segment.fragments.sort(key=lambda f: f.idx)

            # Re-process the text
            FragmentUtils.update_segment_text(session, segment)


class TextUtils:
    """Set of string / text utilities."""

    @staticmethod
    def cer(ref: str, hyp: str) -> float:
        """
        Compute Character Error Rate (CER) between reference and hypothesis.

        CER = (S + D + I) / N
        where
            S = substitutions
            D = deletions
            I = insertions
            N = number of characters in reference

        Args:
            ref (str): Reference text.
            hyp (str): Hypothesis text.

        Returns:
            float: Character Error Rate (CER).
        """

        # Initialise DP matrix
        n, m = len(ref), len(hyp)
        dp = [[0] * (m + 1) for _ in range(n + 1)]

        # Base cases
        for i in range(n + 1):
            dp[i][0] = i
        for j in range(m + 1):
            dp[0][j] = j

        # Fill DP matrix
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = 0 if ref[i - 1] == hyp[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,  # deletion
                    dp[i][j - 1] + 1,  # insertion
                    dp[i - 1][j - 1] + cost,  # substitution
                )

        # Return CER
        distance = dp[n][m]
        return distance / n if n > 0 else float("inf")

    @staticmethod
    def normalize(text: str) -> str:
        """Normalise text.

        When comparing text, it is often useful to normalise it first. This will strip out
        all non-letter characters and collapse whitespace.

        Args:
            text (str): Text to normalise.

        Returns:
            str: Normalised text.
        """

        # Lowercase
        text = text.lower()

        # Remove punctuation (Unicode category "P")
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "P")

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Return cleaned text
        return text
