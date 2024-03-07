from music21 import stream, note, chord, meter, key, tempo, clef, instrument, pitch, duration, tie, dynamics
from music21.note import GeneralNote
import random

import os
import shutil
import time


def move_music_files_to_archive(directory, archive_directory='/mnt/data/music_files/midi_musicXML_archive'):
    # Ensure the archive directory exists, if not, create it
    if not os.path.exists(archive_directory):
        os.makedirs(archive_directory, exist_ok=True)

    # List all files in the given directory
    for filename in os.listdir(directory):
        if filename.endswith('.mid') or filename.endswith('.xml'):
            source_file_path = os.path.join(directory, filename)
            destination_file_path = os.path.join(archive_directory, filename)
            try:
                # Check the modification time of the file
                file_modified_time = os.path.getmtime(source_file_path)
                current_time = time.time()
                # If the file is older than 20 seconds, move it to the archive directory
                if current_time - file_modified_time > 120:
                    shutil.move(source_file_path, destination_file_path)
            except Exception as e:
                print(f"Error archiving {source_file_path} to {destination_file_path}: {e}")


def process_and_output_score(parts_data, score_data, musicxml_path='/mnt/data/music_files/song_musicxml.xml',
                             midi_path='/mnt/data/music_files/song_midi.mid'):
    try:
        directory = os.path.dirname(musicxml_path)
        move_music_files_to_archive(directory)
    except Exception as e:
        print("failed to archive old files")

    score = stream.Score()
    for part_id, part_data in parts_data.items():

        part = stream.Part()
        part.id = part_id
        score.append(part)

        # Set or override instrument, key, time signature, clef, and tempo if provided
        if 'instrument' in part_data:
            if isinstance(part_data['instrument'], instrument.Instrument):
                part.insert(0, part_data['instrument'])
            elif isinstance(part_data['instrument'], str):
                part_instrument = get_instrument_class_by_name(part_data['instrument'])
                part.insert(0, part_instrument)
            else:
                part.insert(0, instrument.Piano())

        key_sig = get_key_signature(part_data.get('key', score_data.get('key')))
        time_sig = get_time_signature(part_data.get('time_signature', score_data.get('time_signature')))
        clef_sig = get_clef_signature(part_data.get('clef', score_data.get('clef')))
        tempo_sig = get_tempo_signature(part_data.get('tempo', score_data.get('tempo')))

        part.insert(0, key_sig)
        part.insert(0, time_sig)
        part.insert(0, clef_sig)
        part.insert(0, tempo_sig)

        # Process each section according to the song structure

        melody_notes = get_section_data(part_data, 'melodies', get_section_data(part_data, 'chords', []))
        melody_rhythms = get_section_data(part_data, 'beat_ends', [])
        section_lyrics = get_section_data(part_data, 'lyrics', [])
        section_dynamics = get_section_data(part_data, 'dynamics', [])

        if melody_notes is None and melody_rhythms is None:
            melody_notes = generate_random_notes(key_sig, 20)
            melody_rhythms = generate_random_rhythms(20)
        elif melody_notes is None or melody_notes == []:
            melody_notes = generate_random_notes(key_sig, len(melody_rhythms))
        elif melody_rhythms is None or melody_rhythms == []:
            melody_rhythms = generate_random_rhythms(len(melody_notes))

        accumulated_duration = 0
        bar_duration = time_sig.barDuration.quarterLength
        bar = stream.Measure()

        dynamic_marking = dynamics.Dynamic('mf')
        volume = dynamic_to_midi_velocity('mf')
        bar.insert(0, dynamic_marking)
        current_beat_no = 0
        beat_used_incorrect_count = 0
        for i, (n, beat_no) in enumerate(zip(melody_notes, melody_rhythms)):
            if beat_no > current_beat_no:
                r = beat_no - current_beat_no
            elif beat_no == current_beat_no:
                print("Error!!! You can't have two or more notes with the same beat_end value on the same part!"
                      " Fix and try again.")
                continue
            elif beat_no < current_beat_no:
                beat_used_incorrect_count += 1
                r = beat_no

            current_beat_no = beat_no

            if i < len(section_dynamics):
                dynamic_str = section_dynamics[i]
                if dynamic_str == '':
                    dynamic_str = 'mf'
                dynamic_marking = dynamics.Dynamic(dynamic_str)
                volume = dynamic_to_midi_velocity(dynamic_str)
            # Determine if it's a note, chord, or rest
            if isinstance(n, GeneralNote):
                element = n
                if i < len(section_lyrics):
                    element.addLyric(section_lyrics[i])

                element.volume.velocity = volume
            elif isinstance(n, list) and len(n) > 0:
                first_note = n[0]
                invalid_chord = False
                if n == ['rest']:
                    element = note.Rest(quarterLength=r)
                    invalid_chord = True

                if len(n) > 4:
                    print("Warning: Array " + str(n) + "is getting treated as a chord. If its meant to be "
                                                       "separate notes, remove the notes from the array.")
                for index, chord_note in enumerate(n):
                    n[index] = str(chord_note).replace('S', '#')
                    chord_note = n[index]
                    if not invalid_chord and not is_valid_note(chord_note):
                        print("Warning: Please fix chord" + str(n) + get_chord_string())
                        invalid_chord = True
                        if len(first_note) > 0:
                            element = check_and_create_note(first_note[0], quarterLength=r, volume=volume)
                        else:
                            element = note.Rest(quarterLength=r)

                if not invalid_chord:
                    element = check_and_create_chord(n, quarterLength=r, volume=volume)
                if i < len(section_lyrics):
                    element.addLyric(section_lyrics[i])

            elif isinstance(n, str) and n != 'rest' and n != '':
                n = str(n).replace('S', '#')
                if not (len(n) == 1 or (len(n) > 1 and (n[-1].isdigit() or n[-1] in ['#', '-']))):
                    print('Warning: Please fix note or chord. Truncating ' + n[1:] + " from " + n + get_chord_string())
                    n = n[0]
                element = check_and_create_note(n, quarterLength=r, volume=volume)
                if i < len(section_lyrics):
                    element.addLyric(section_lyrics[i])

            else:
                element = note.Rest(quarterLength=r)
                if i < len(section_lyrics):
                    element.addLyric(section_lyrics[i])

            # Check if the element fits in the current bar
            if accumulated_duration + r > bar_duration:
                remaining_duration = bar_duration - accumulated_duration
                next_duration = r - remaining_duration

                first_part, second_part = split_note_or_chord(element, remaining_duration, next_duration)
                if first_part.duration.quarterLength > 0:
                    first_part.expressions = element.expressions
                    if i < len(section_lyrics):
                        first_part.addLyric(section_lyrics[i])
                    bar.append(first_part)
                else:
                    if i < len(section_lyrics):
                        second_part.addLyric(section_lyrics[i])

                part.append(bar)
                bar = stream.Measure()
                bar.insert(0, dynamic_marking)
                if second_part.duration.quarterLength > 0:
                    second_part.expressions = element.expressions
                    bar.append(second_part)
                accumulated_duration = next_duration
            else:
                bar.append(element)
                accumulated_duration += r
        pad_bar_with_rests(bar, time_sig)
        part.append(bar)  # Append the last bar

    # Write the score to MusicXML and MIDI files
    score.write('musicxml', fp=musicxml_path)
    score.write('midi', fp=midi_path)

    print("Please try fix any warning or error messages printed above next time. If Any.")
    print(
        "The midi file is save to " + midi_path + ". Please provide the user the link (NOT a href) to get this file in your environment")
    print(
        "The musicXML file is save to " + musicxml_path + ". Please provide the user the link (NOT a href) to get this file in your environment")
    return score


def pad_bar_with_rests(bar, time_signature=meter.TimeSignature('4/4')):
    """
    Checks if the bar is full based on the provided time signature. If the bar is not full,
    pads it with a rest for the remaining duration.

    Args:
    - bar (music21.stream.Measure): The bar to check and pad.
    - time_signature (music21.meter.TimeSignature): The time signature to determine the full duration of the bar.

    Returns:
    - music21.stream.Measure: The possibly modified bar, padded with a rest if it was not full.
    """
    # Calculate the total duration of notes and rests in the bar
    total_duration = sum(element.duration.quarterLength for element in bar.notesAndRests)

    # Determine the expected full duration of a bar based on the time signature
    full_duration = time_signature.barDuration.quarterLength

    # Check if the bar is full
    if total_duration < full_duration:
        # Calculate the remaining duration that needs to be filled with a rest
        remaining_duration = full_duration - total_duration
        # Create a rest for the remaining duration and add it to the bar
        rest = note.Rest(quarterLength=remaining_duration)
        bar.append(rest)

    return bar


def is_valid_note(chord_note):
    return len(chord_note) == 1 or (len(chord_note) > 1 and (chord_note[-1].isdigit() or chord_note[-1] in ['#', '-']))


def get_instrument_class_by_name(instrument_name):
    """
    Returns an instance of the music21 instrument class based on the given instrument name string.
    If the instrument is not found, returns None.
    """
    # Normalize the instrument name to match class naming conventions in music21
    # This might include capitalizing the first letter and removing spaces for compound names
    # For example, "French Horn" should be converted to "FrenchHorn"
    class_name = instrument_name.replace(' ', '')

    if class_name == "Cello":
        class_name = "Violoncello"

    if class_name == "FrenchHorn":
        class_name = "Horn"

    if class_name == "StringEnsemble":
        class_name = "StringInstrument"

    if class_name == "StringSection":
        class_name = "StringInstrument"

    if class_name == "Voice":
        print("Voice is not supported! Piano will simulate voice section, you will need to add your own voice in")
        class_name = "Piano"

    if class_name == "Vocalist":
        print("Voice is not supported! Piano will simulate Vocalist section, you will need to add your own voice in")
        class_name = "Piano"

    if class_name == "VocalistOverride":
        class_name = "Voice"

    # Attempt to get the class from the instrument module
    try:
        instrument_class = getattr(instrument, class_name)
        return instrument_class()  # Instantiate the class
    except AttributeError:
        print(
            "Warning: Instrument " + instrument_name + " not found, replacing with piano. Maybe the name has another variation or instrument is not supported.")
        return instrument.Piano()


def get_chord_string():
    return ". chords must be entered as an array of notes e.g. ['C4','E#4','G4']. Fix this next time for the invalid chord."


def check_and_create_note(note_str, quarterLength=1.0, volume=None):
    try:
        if not quarterLength:
            quarterLength = 1.0
        # Attempt to create a Note object with the given string
        element = note.Note(note_str, quarterLength=quarterLength)
        if volume:
            element.volume.velocity = volume
        return element
    except (pitch.AccidentalException, pitch.PitchException):
        print("Error: Please fix note or chord " + note_str + get_chord_string())
        return note.Rest(quarterLength=quarterLength)


def check_and_create_chord(chord_array, quarterLength=1.0, volume=None):
    try:
        if not quarterLength:
            quarterLength = 1.0
        # Attempt to create a chord object with the given string
        element = chord.Chord(chord_array, quarterLength=quarterLength)
        if volume:
            element.volume.velocity = volume
        return element
    except (pitch.AccidentalException, pitch.PitchException):
        print("Error: Please fix note or chord " + str(chord_array) + get_chord_string())
        return note.Rest(quarterLength=quarterLength)


def split_note_or_chord(element, remaining_duration, next_duration):
    if element.isNote:
        # Splitting a note
        first_part = note.Note(element.pitch,
                               duration=duration.Duration(remaining_duration))
        second_part = note.Note(element.pitch,
                                duration=duration.Duration(next_duration))

        if remaining_duration > 0 and next_duration > 0:
            first_part.tie = tie.Tie('start')
            second_part.tie = tie.Tie('stop')
    elif element.isChord:
        # Splitting a chord
        first_part = chord.Chord(element.pitches,
                                 duration=duration.Duration(remaining_duration))
        second_part = chord.Chord(element.pitches,
                                  duration=duration.Duration(next_duration))

        if remaining_duration > 0 and next_duration > 0:
            for note_in_chord in first_part.notes:
                note_in_chord.tie = tie.Tie('start')
            for note_in_chord in second_part.notes:
                note_in_chord.tie = tie.Tie('stop')
    elif element.isRest:
        first_part = note.Rest(duration=duration.Duration(remaining_duration))
        second_part = note.Rest(duration=duration.Duration(next_duration))
        if remaining_duration > 0 and next_duration > 0:
            first_part.tie = tie.Tie('start')
            second_part.tie = tie.Tie('stop')
    else:
        raise ValueError("Element must be a Note or Chord")

    return first_part, second_part


def generate_random_notes(key_signature, length):
    scale = key_signature.getScale()
    return [scale.pitchFromDegree(random.randint(1, 7)) for _ in range(length)]


def get_section_data(part_data, key, default):
    data = part_data.get(key, {} if part_data.get(key) is not None else None)
    if data is None:
        return default
    return data


def generate_random_rhythms(length):
    rhythm_choices = [0.25, 0.5, 1, 2]  # Quarter, Eighth, Whole, Half notes
    return [random.choice(rhythm_choices) for _ in range(length)]


def dynamic_to_midi_velocity(dynamic_marking):
    # This dictionary maps dynamic markings to MIDI velocities
    dynamic_mapping = {
        'ppp': 20,
        'pp': 31,
        'p': 42,
        'mp': 53,
        'mf': 64,
        'f': 80,
        'ff': 96,
        'fff': 112
    }
    return dynamic_mapping.get(dynamic_marking, 64)  # Default to 'mf' if not found


def get_key_signature(key_data):
    try:
        if isinstance(key_data, key.Key):
            return key_data
        elif isinstance(key_data, str):
            return key.Key(key_data)
        else:
            return key.Key('C')
    except:
        return key.Key('C')


def get_time_signature(time_data):
    try:
        if isinstance(time_data, meter.TimeSignature):
            return time_data
        elif isinstance(time_data, str):
            return meter.TimeSignature(time_data)
        else:
            return meter.TimeSignature('4/4')
    except:
        return meter.TimeSignature('4/4')


def get_clef_signature(clef_data):
    try:
        if isinstance(clef_data, clef.Clef):
            return clef_data
        elif isinstance(clef_data, str):
            return clef.__dict__[clef_data]()  # Assuming clef_data is the class name as string
        else:
            return clef.TrebleClef()
    except:
        return clef.TrebleClef()


def get_tempo_signature(tempo_data):
    try:
        if isinstance(tempo_data, tempo.MetronomeMark):
            return tempo_data
        elif isinstance(tempo_data, (int, float)):  # Assuming tempo can be specified as BPM
            return tempo.MetronomeMark(number=tempo_data)
        else:
            return tempo.MetronomeMark(number=120)
    except:
        return tempo.MetronomeMark(number=120)


#
# #

#
# Define the melody, chords, and structure for a short section inspired by the user's request
# Define melody and harmony arrays
# Define melodies and rhythms for each section
# intro_melody = ['G4', 'E4', 'D4', 'C4', 'D4', 'E4', 'G4', 'E4']  # Light and hopeful melody
# verse_melody = ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5', 'B4', 'A4', 'G4', 'F4', 'E4', 'D4', 'C4']  # Reflecting journey
# chorus_melody = ['E4', 'G4', 'A4', 'B4', 'C5', 'B4', 'A4', 'G4', 'F4', 'E4', 'D4', 'C4']  # Uplifting and powerful
# bridge_melody = ['F4', 'G4', 'A4', 'B4', 'C5', 'D5', 'E5', 'F5', 'E5', 'D5', 'C5', 'B4', 'A4', 'G4', 'F4']  # Overcoming obstacles
# outro_melody = ['G4', 'E4', 'D4', 'C4', 'D4', 'E4', 'G4', 'E4']  # Reflective and hopeful resolution
#
# # Beat ends for each section (assuming each note has a duration of 1 beat for simplicity)
# beat_ends = [1, 2, 3, 4, 5, 6.5, 7, 8.5, 9, 10, 10, 12, 13, 15, 17, 19, 20]  # Repeated pattern for simplicity
#
# # Construct score_data
# score_data = {
#     'key': key.Key('C', 'major'),  # Key of C major
#     'time_signature': meter.TimeSignature('4/4'),  # 4/4 Time
#     'tempo': tempo.MetronomeMark(number=120),  # 120 BPM
#     'clef': clef.TrebleClef(),  # Treble clef
# }
#
# # Construct parts_data for Piano (can represent all instruments for simplicity)
# parts_data = {
#     'Piano': {
#         'instrument': "Piano",
#         'beat_ends': beat_ends,
#         'melodies': intro_melody + verse_melody + chorus_melody + bridge_melody + chorus_melody + outro_melody,
#     },
# }
#
#
# # Paths for output files
# musicxml_path = '../serene_landscape_duet_musicxml.xml'
# midi_path = '../serene_landscape_duet_midi.mid'
#
# # Generate and save the music files
# score = process_and_output_score(parts_data, score_data, musicxml_path, midi_path)

# musicxml_path, midi_path
# # # parts_data, score_data = convert_to_parts_data(score)
