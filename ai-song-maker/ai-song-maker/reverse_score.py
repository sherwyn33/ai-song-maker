from fractions import Fraction

from music21 import note, chord, meter, tempo, clef, percussion
import json
from typing import Tuple, Dict, Any

def convert_to_parts_data(score) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Converts a music21 stream.Score object into parts_data and score_data structures,
    assuming all parts have just one section and ignoring measures.
    """
    parts_data = {}
    song_structure = ["section_1"]  # Assuming all parts have just one section
    key_signature = score.analyze('key')
    time_signature = score.recurse().getElementsByClass(meter.TimeSignature)[0]
    bpm = score.metronomeMarkBoundaries()[0][2].number if score.metronomeMarkBoundaries() else 120

    for part in score.parts:
        part_name = part.partName or "Part"
        if part_name in parts_data:
            part_name = part_name + "X"
        # Attempt to extract the instrument from the part, default to Piano if not present
        part_instrument = part.getInstrument()
        instrument_name = part_instrument.instrumentName if part_instrument else "Piano"

        melodies = []
        rhythms = []
        lyrics = []
        dynamics = []
        current_beat_no = 0
        for element in part.recurse().notesAndRests:
            try:
                current_beat_no += element.duration.quarterLength
                rhythms.append(current_beat_no)
                lyrics.append(element.lyric if element.lyric else '')
                if not isinstance(element, note.Rest) and element.volume:
                    dynamics.append(velocity_to_dynamic(element.volume.velocity))

                if isinstance(element, note.Note):
                    melodies.append(element.nameWithOctave)

                elif isinstance(element, chord.Chord):
                    melody_chord = [n.nameWithOctave for n in element.notes]
                    melodies.append(melody_chord)

                elif isinstance(element, percussion.PercussionChord):
                    melody_chord = [n.displayName for n in element.notes]
                    melodies.append(melody_chord)

                elif isinstance(element, note.Rest):
                    melodies.append('rest')

                else:
                    melodies.append('rest')
            except:
                melodies.append('')
                rhythms.append(current_beat_no)
                dynamics.append('mf')


        parts_data[part_name] = {
            'instrument': instrument_name,
            'melodies': melodies,
            'beat_ends': rhythms,
            'dynamics': dynamics
        }
        if any(lyrics):
            parts_data['lyrics'] = lyrics

    score_data = {
        'song_structure': song_structure,
        'key': key_signature,
        'time_signature': time_signature,
        'tempo': tempo.MetronomeMark(number=bpm),
        'clef': clef.TrebleClef(),  # Simplification for this example
    }
    string_to_print = "Please read these json outputs accurately, it will be useful for this answer and future answers\n"
    string_to_print += 'parts_data json output from score is: \n'
    string_to_print += json.dumps(parts_data, default=custom_serializer)

    string_to_print += '\nscore_data json output from score is: \n'
    string_to_print += "\nuse music21 python classes to change music21 objects in score_data e.g. key.Key('C', 'Major'), meter.TimeSignature('4/4'), tempo.MetronomeMark(number=120), clef.TrebleClef()\n"
    string_to_print += json.dumps(score_data, default=str)

    return parts_data, score_data, string_to_print


def custom_serializer(obj):
    if isinstance(obj, Fraction):
        # Convert Fraction to a string or a float, depending on your needs
        return float(obj)  # or float(obj) for a numerical representation
    return obj

def velocity_to_dynamic(velocity):
    if not velocity:
        return 'mf'
    # Original mapping from dynamic markings to MIDI velocities
    dynamic_mapping = {
        'pp': 31,
        'p': 42,
        'mp': 53,
        'mf': 64,
        'f': 80,
        'ff': 96,
    }

    # Invert the dictionary to create a reverse mapping
    reverse_mapping = {v: k for k, v in dynamic_mapping.items()}

    # Find the closest velocity in the reverse mapping
    closest_velocity = min(reverse_mapping.keys(), key=lambda x: abs(x - velocity))

    return reverse_mapping[closest_velocity]

