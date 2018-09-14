void MatchBBox(const vector<NormalizedBBox>& gt_bboxes,
    const vector<NormalizedBBox>& pred_bboxes, const int label,
    const MatchType match_type, const float overlap_threshold,
    const bool ignore_cross_boundary_bbox,
    vector<int>* match_indices, vector<float>* match_overlaps) {
	// ����gt_bboxes, decode_prior_bboxes, label������labelΪ-1
	//ignore_cross_boundary_bbox = False
	// �õ���match_indices��prior�Ĵ�СN����ʾÿ��prior���Ǹ�gtƥ�䣬û��ƥ��Ϊ-1
	// ��Ӧ��overlaps�������iou��
  int num_pred = pred_bboxes.size();
  match_indices->clear();
  match_indices->resize(num_pred, -1);
  match_overlaps->clear();
  match_overlaps->resize(num_pred, 0.);

  int num_gt = 0;
  vector<int> gt_indices;
  // ĿǰlabelΪ-1��pred_box�ǲ��������ģ�priorͬ���е�gt����ƥ��
  if (label == -1) {
    // label -1 means comparing against all ground truth.
    num_gt = gt_bboxes.size();
    for (int i = 0; i < num_gt; ++i) {
      gt_indices.push_back(i);
    }
  }
  if (num_gt == 0) {
    return;
  }

  // Store the positive overlap between predictions and ground truth.
  // ��Ŀ��overlaps N x num_gt
  // match_overlaps��¼��ǰpriors��������gtƥ������ֵ�����ֵ�����ǵ�����ֵ�ġ�
  map<int, map<int, float> > overlaps;
  for (int i = 0; i < num_pred; ++i) {
    if (ignore_cross_boundary_bbox && IsCrossBoundaryBBox(pred_bboxes[i])) {
      (*match_indices)[i] = -2;
      continue;
    }
    for (int j = 0; j < num_gt; ++j) {
      float overlap = JaccardOverlap(pred_bboxes[i], gt_bboxes[gt_indices[j]]);
      if (overlap > 1e-6) {
        (*match_overlaps)[i] = std::max((*match_overlaps)[i], overlap);
        overlaps[i][j] = overlap;
      }
    }
  }

  // Bipartite matching.
  vector<int> gt_pool;
  for (int i = 0; i < num_gt; ++i) {
    gt_pool.push_back(i);
  }
  // ÿ��Ѱ��ƥ������overlap����¼��Ӧ��gt����pred����ѡ����gt��pred�����ٿ��ǡ�
  // ����gt��ֱ��ereas���ɣ�����pred���ǲ鿴��־λ��
  // ÿ��gt��ҪѰ��һ����ÿ��Ѱ�Ҿ��Ǳ���N * gt����Ѱ��һ�����ġ�
  // ��������ı���������N * gt^2������gt������ѭ����
  while (gt_pool.size() > 0) {
    // Find the most overlapped gt and cooresponding predictions.
    int max_idx = -1;
    int max_gt_idx = -1;
    float max_overlap = -1;
    for (map<int, map<int, float> >::iterator it = overlaps.begin();
         it != overlaps.end(); ++it) {
      // ��i��prior
    	int i = it->first;
      if ((*match_indices)[i] != -1) {
        // The prediction already has matched ground truth or is ignored.
        continue;
      }

      for (int p = 0; p < gt_pool.size(); ++p) {
        int j = gt_pool[p];
        // ���е�gt�Ƚ�һ�£����it��û��j����ʾ���i��jû��overlap��
        // ���������label=-1��������֣�һֱ����overlap��û�е�ʱ��Ҳ����
        // label��Ϊ-1��ʱ����ʱ��û�йؼ���keyΪj����ʾû�м����overlap��
        if (it->second.find(j) == it->second.end()) {
          // No overlap between the i-th prediction and j-th ground truth.
          continue;
        }
        // Find the maximum overlapped pair.
        if (it->second[j] > max_overlap) {
          // If the prediction has not been matched to any ground truth,
          // and the overlap is larger than maximum overlap, update.
          max_idx = i;
          max_gt_idx = j;
          max_overlap = it->second[j];
        }
      }
    }
    if (max_idx == -1) {
      // Cannot find good match.
      break;
    } else {
    	// max_idx��Ӧ��pred��������û�б�ƥ����ġ�
    	// ��¼��֮ƥ���gt��������ͬʱ��¼overlap
      CHECK_EQ((*match_indices)[max_idx], -1);
      (*match_indices)[max_idx] = gt_indices[max_gt_idx];
      (*match_overlaps)[max_idx] = max_overlap;
      // Erase the ground truth.
      // ��gtɾ������һ��gtֻƥ��һ�Ρ�
      gt_pool.erase(std::find(gt_pool.begin(), gt_pool.end(), max_gt_idx));
    }
  }

  switch (match_type) {
    case MultiBoxLossParameter_MatchType_BIPARTITE:
      // Already done.
      break;
    case MultiBoxLossParameter_MatchType_PER_PREDICTION:
      // Get most overlaped for the rest prediction bboxes.
    	// ��û��ƥ���prior����Ѱ��һ��gt��������Զ�Ӧ��ͬ��gt��
    	// ֻҪoverlap����һ������ֵ
      for (map<int, map<int, float> >::iterator it = overlaps.begin();
           it != overlaps.end(); ++it) {
        int i = it->first;
        if ((*match_indices)[i] != -1) {
          // The prediction already has matched ground truth or is ignored.
          continue;
        }
        int max_gt_idx = -1;
        float max_overlap = -1;
        for (int j = 0; j < num_gt; ++j) {
          if (it->second.find(j) == it->second.end()) {
            // No overlap between the i-th prediction and j-th ground truth.
            continue;
          }
          // Find the maximum overlapped pair.
          float overlap = it->second[j];
          if (overlap >= overlap_threshold && overlap > max_overlap) {
            // If the prediction has not been matched to any ground truth,
            // and the overlap is larger than maximum overlap, update.
            max_gt_idx = j;
            max_overlap = overlap;
          }
        }
        if (max_gt_idx != -1) {
          // Found a matched ground truth.
          CHECK_EQ((*match_indices)[i], -1);
          (*match_indices)[i] = gt_indices[max_gt_idx];
          (*match_overlaps)[i] = max_overlap;
        }
      }
      break;
    default:
      LOG(FATAL) << "Unknown matching type.";
      break;
  }

  return;
}
