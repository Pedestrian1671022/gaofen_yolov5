import os
import time


def iou(bbox1, bbox2):
    bbox1 = [float(x) for x in bbox1]
    bbox2 = [float(x) for x in bbox2]
    (x0_1, y0_1, x1_1, y1_1) = bbox1
    (x0_2, y0_2, x1_2, y1_2) = bbox2
    overlap_x0 = max(x0_1, x0_2)
    overlap_y0 = max(y0_1, y0_2)
    overlap_x1 = min(x1_1, x1_2)
    overlap_y1 = min(y1_1, y1_2)
    if overlap_x1 - overlap_x0 <= 0 or overlap_y1 - overlap_y0 <= 0:
        return 0
    size_1 = (x1_1 - x0_1) * (y1_1 - y0_1)
    size_2 = (x1_2 - x0_2) * (y1_2 - y0_2)
    size_intersection = (overlap_x1 - overlap_x0) * (overlap_y1 - overlap_y0)
    size_union = size_1 + size_2 - size_intersection
    return size_intersection / size_union


def track_iou(detections, tracks_active, sigma_l, sigma_h, sigma_iou, t_life, t_loss, id):
    tracks_finished = []
    dets_1 = [det for det in detections if det['score'] >= sigma_l and det['cls'] == 0]
    dets_2 = [det for det in detections if det['score'] >= sigma_l and det['cls'] == 2]
    updated_tracks = []
    for track in tracks_active:
        if track['cls'] == 0:
            if len(dets_1) > 0:
                best_match = max(dets_1, key=lambda x: iou(track['bboxes'], x['bbox']))
                if iou(track['bboxes'], best_match['bbox']) >= sigma_iou:
                    track['bboxes'] = best_match['bbox']
                    track['max_score'] = max(track['max_score'], best_match['score'])
                    track['life_time'] += 1
                    track['loss_time'] = 0
                    updated_tracks.append(track)
                    del dets_1[dets_1.index(best_match)]
                    if track['max_score'] >= sigma_h and track['life_time'] >= t_life:
                        if track['id'] == 0:
                            id += 1
                            track['id'] = id
                        tracks_finished.append(track)
            if len(updated_tracks) == 0 or track is not updated_tracks[-1]:
                track['loss_time'] += 1
                if track['loss_time'] > 0:
                    track['life_time'] = 0
                if track['loss_time'] >= t_loss:
                    tracks_active.remove(track)
        else:
            if len(dets_2) > 0:
                best_match = max(dets_2, key=lambda x: iou(track['bboxes'], x['bbox']))
                if iou(track['bboxes'], best_match['bbox']) >= sigma_iou:
                    track['bboxes'] = best_match['bbox']
                    track['max_score'] = max(track['max_score'], best_match['score'])
                    track['life_time'] += 1
                    track['loss_time'] = 0
                    updated_tracks.append(track)
                    del dets_2[dets_2.index(best_match)]
                    if track['max_score'] >= sigma_h and track['life_time'] >= t_life:
                        if track['id'] == 0:
                            id += 1
                            track['id'] = id
                        tracks_finished.append(track)
            if len(updated_tracks) == 0 or track is not updated_tracks[-1]:
                track['loss_time'] += 1
                if track['loss_time'] > 2:
                    track['life_time'] = 0
                if track['loss_time'] >= t_loss:
                    tracks_active.remove(track)
    new_tracks_1 = [
        {'bboxes': det['bbox'], 'max_score': det['score'], 'life_time': 1, 'loss_time': 0, 'id': 0, 'cls': det['cls']}
        for det in dets_1]
    new_tracks_2 = [
        {'bboxes': det['bbox'], 'max_score': det['score'], 'life_time': 1, 'loss_time': 0, 'id': 0, 'cls': det['cls']}
        for det in dets_2]
    tracks_active = tracks_active + new_tracks_1 + new_tracks_2
    return tracks_finished, tracks_active, id


def convertBack(xmin, ymin, xmax, ymax, conf, cls):
    xmin = int(xmin) - 2
    xmax = int(xmax) + 2
    ymin = int(ymin) - 2
    ymax = int(ymax) + 2
    return [xmin, ymin, xmax, ymax], conf, int(cls)


def get_image_list(path):
    image_names = []
    for maindir, subdir, file_name_list in os.walk(path):
        for filename in file_name_list:
            apath = os.path.join(maindir, filename)
            image_names.append(apath)
    return image_names


def image_demo(input_path, output_path):
    start_time = time.time()
    inference_times = []
    nms_times = []
    track_times = []
    for subdir in os.listdir(os.path.join(input_path)):
        lines = []
        tracks_active = []
        id = 0
        for yolotxt in sorted(os.listdir(os.path.join(input_path, subdir, 'dts'))):
            bboxes = []
            with open(os.path.join(input_path, subdir, 'dts', yolotxt), 'r') as f:
                for line in f.readlines():
                    splitLine = line.split(" ")
                    idClass = splitLine[0]
                    xmin = int((float(splitLine[1]) - float(splitLine[3]) / 2) * 1920)
                    ymin = int((float(splitLine[2]) - float(splitLine[4]) / 2) * 1080)
                    xmax = int((float(splitLine[3])) * 1920) + xmin
                    ymax= int((float(splitLine[4])) * 1080) + ymin
                    conf = float(splitLine[5])
                    bboxes.append([xmin, ymin, xmax, ymax, conf, idClass])
            track_start_time = time.time()
            bboxes = [convertBack(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]), float(bbox[4]),
                                  float(bbox[5])) for bbox in bboxes]
            detections = [{'bbox': bbox, 'score': conf, 'cls': cls} for bbox, conf, cls in bboxes]
            tracks_finished, tracks_active, id = track_iou(detections, tracks_active, 0.05, 0.4, 0.01, 2, 2, id)
            for track_finished in tracks_finished:
                bbox = track_finished['bboxes']
                line = '{},{},{},{},{},{},{},{},{}'.format(int(yolotxt[2:-4]), track_finished['id'], bbox[0] + 2,
                                                           bbox[1] + 2, bbox[2] - bbox[0] - 4, bbox[3] - bbox[1] - 4, 1,
                                                           track_finished['cls'], 1)
                _lines = lines
                flag_1 = False
                # flag_2 = False
                # flag_3 = False
                # flag_4 = False
                for _line in _lines[max(0, len(_lines) - 1000):]:
                    if _line.startswith('{},{},'.format(int(yolotxt[2:-4]) - 1, track_finished['id'])):
                        flag_1 = True
                    # if _line.startswith('{},{},'.format(int(yolotxt[2:-4]) - 2, track_finished['id'])):
                    #     flag_2 = True
                    # if _line.startswith('{},{},'.format(int(yolotxt[2:-4]) - 3, track_finished['id'])):
                    #     flag_3 = True
                    # if _line.startswith('{},{},'.format(int(yolotxt[2:-4]) - 4, track_finished['id'])):
                    #     flag_4 = True
                if not flag_1:
                    lines.append('{},{},{},{},{},{},{},{},{}'.format(int(yolotxt[2:-4]) - 1, track_finished['id'],
                                                                     bbox[0] + 2, bbox[1] + 2, bbox[2] - bbox[0] - 4,
                                                                     bbox[3] - bbox[1] - 4, 1, track_finished['cls'],
                                                                     1))
                # if not flag_2:
                #     lines.append('{},{},{},{},{},{},{},{},{}'.format(int(yolotxt[2:-4]) - 2, track_finished['id'],
                #                                                      bbox[0] + 2, bbox[1] + 2, bbox[2] - bbox[0] - 4,
                #                                                      bbox[3] - bbox[1] - 4, 1, track_finished['cls'],
                #                                                      1))
                # if not flag_3:
                #     lines.append('{},{},{},{},{},{},{},{},{}'.format(int(yolotxt[2:-4]) - 3, track_finished['id'],
                #                                                      bbox[0] + 2, bbox[1] + 2, bbox[2] - bbox[0] - 4,
                #                                                      bbox[3] - bbox[1] - 4, 1, track_finished['cls'],
                #                                                      1))
                # if not flag_4:
                #     lines.append('{},{},{},{},{},{},{},{},{}'.format(int(yolotxt[2:-4]) - 4, track_finished['id'],
                #                                                      bbox[0] + 2, bbox[1] + 2, bbox[2] - bbox[0] - 4,
                #                                                      bbox[3] - bbox[1] - 4, 1, track_finished['cls'],
                #                                                      1))
                lines.append(line)
            track_times.append(time.time() - track_start_time)
        with open(os.path.join(output_path, subdir + '.txt'), 'w') as f:
            lines.sort(key=lambda line: (int(line.split(',')[1]), int(line.split(',')[0])))
            for line in lines:
                f.write(line + '\n')
    print("time:{},inference_time:{},nms_time:{},track_time:{}".format(time.time() - start_time, sum(inference_times),
                                                                       sum(nms_times), sum(track_times)))


def main():
    image_demo('/input_path', '/output_path')


if __name__ == "__main__":
    main()