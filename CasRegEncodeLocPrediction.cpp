template <typename Dtype>
void CasRegEncodeLocPrediction(const vector<LabelBBox>& all_loc_preds,
      const map<int, vector<NormalizedBBox> >& all_gt_bboxes,
      const vector<map<int, vector<int> > >& all_match_indices,
      const vector<NormalizedBBox>& prior_bboxes,
      const vector<vector<float> >& prior_variances,
      const MultiBoxLossParameter& multibox_loss_param,
      Dtype* loc_pred_data, Dtype* loc_gt_data,
	  const vector<LabelBBox>& all_arm_loc_preds) {
  // ����encode�����������Dtype* loc_pred_data, Dtype* loc_gt_data,��
  // ͼƬ��Ŀ
  // ʹ��refined priors��gt���б��룬ֻ���벢�޸�indicesָ���ģ�Ҳ����ƥ��ġ�
  int num = all_loc_preds.size();
  // CHECK_EQ(num, all_match_indices.size());
  // Get parameters.
  const CodeType code_type = multibox_loss_param.code_type();
  const bool encode_variance_in_target =
      multibox_loss_param.encode_variance_in_target();
  // �Ƿ���õ����м���жϣ��鿴�˲���Ҫ
  // use_prior_for_matchingΪtrue
  const bool bp_inside = multibox_loss_param.bp_inside();
  const bool use_prior_for_matching =
      multibox_loss_param.use_prior_for_matching();
  int count = 0;
  for (int i = 0; i < num; ++i) {
    //apply arm_loc_preds to prior_box
    // decode arm_loc_preds by prior_box
    // iͼ����ǰͼarmԤ��
    const vector<NormalizedBBox>& arm_loc_preds =
        all_arm_loc_preds[i].find(-1)->second;
    // ��Ž��������ֽ�һ���룿�õ�����refine priors��
    // ��ǰ��Ѱ��match��һ���ķ�ʽ��������β������������ˣ��Ѿ���match�������ˡ�
    // all_match_indices
    vector<NormalizedBBox> decode_prior_bboxes;
    bool clip_bbox = false;
    DecodeBBoxes(prior_bboxes, prior_variances,
    		code_type, encode_variance_in_target, clip_bbox,
			arm_loc_preds, &decode_prior_bboxes);
    // indices guide matching between all_loc_preds and gt.
    // ��ǰ��find match�����Ͻ�һ������ƥ��armƥ���refine box����Ӧ�Ľ���encode��
    // ��ǰͼarm��ƥ��������
    for (map<int, vector<int> >::const_iterator
         it = all_match_indices[i].begin();
         it != all_match_indices[i].end(); ++it) {
      // ����ֻ��һ��key��label=-1
      const int label = it->first;
      const vector<int>& match_index = it->second;
      // һ��Ҫ�ܱ�֤����
      CHECK(all_loc_preds[i].find(label) != all_loc_preds[i].end());
      // �ҵ�ƥ���Ԥ�⣬������Ҫ�������ֵ�ŵ������loc_pred_data���档
      // ��Ҫֻ�ǳ�ȡ���á�
      const vector<NormalizedBBox>& loc_pred =
          all_loc_preds[i].find(label)->second;
      for (int j = 0; j < match_index.size(); ++j) {
        if (match_index[j] <= -1) {
          continue;
        }
        // Store encoded ground truth.
        const int gt_idx = match_index[j];
        CHECK(all_gt_bboxes.find(i) != all_gt_bboxes.end());
        CHECK_LT(gt_idx, all_gt_bboxes.find(i)->second.size());
        const NormalizedBBox& gt_bbox = all_gt_bboxes.find(i)->second[gt_idx];
        NormalizedBBox gt_encode;
        CHECK_LT(j, decode_prior_bboxes.size());
        // �ҵ���Ӧ��gt���ö�Ӧ��refine����prior��gt���б��룬�õ�loc_gt_data
        EncodeBBox(decode_prior_bboxes[j], prior_variances[j], code_type,
                   encode_variance_in_target, gt_bbox, &gt_encode);
        // ����gt���б���Ľ��
        loc_gt_data[count * 4] = gt_encode.xmin();
        loc_gt_data[count * 4 + 1] = gt_encode.ymin();
        loc_gt_data[count * 4 + 2] = gt_encode.xmax();
        loc_gt_data[count * 4 + 3] = gt_encode.ymax();
        // Store location prediction.
				CHECK_LT(j, loc_pred.size());
				//Ĭ���ǲ�����bp_inside�ģ������ǳ����߽�Ĵ��ڡ�
				if (bp_inside) {
					NormalizedBBox match_bbox = decode_prior_bboxes[j];
					if (!use_prior_for_matching) {
						const bool clip_bbox = false;
						DecodeBBox(decode_prior_bboxes[j], prior_variances[j], code_type,
											 encode_variance_in_target, clip_bbox, loc_pred[j],
											 &match_bbox);
					}
					// When a dimension of match_bbox is outside of image region, use
					// gt_encode to simulate zero gradient.
					loc_pred_data[count * 4] =
							(match_bbox.xmin() < 0 || match_bbox.xmin() > 1) ?
							gt_encode.xmin() : loc_pred[j].xmin();
					loc_pred_data[count * 4 + 1] =
							(match_bbox.ymin() < 0 || match_bbox.ymin() > 1) ?
							gt_encode.ymin() : loc_pred[j].ymin();
					loc_pred_data[count * 4 + 2] =
							(match_bbox.xmax() < 0 || match_bbox.xmax() > 1) ?
							gt_encode.xmax() : loc_pred[j].xmax();
					loc_pred_data[count * 4 + 3] =
							(match_bbox.ymax() < 0 || match_bbox.ymax() > 1) ?
							gt_encode.ymax() : loc_pred[j].ymax();
				} else {
					// ��ȡ��Ӧ��Ԥ�����������������߼���loss
          loc_pred_data[count * 4] = loc_pred[j].xmin();
          loc_pred_data[count * 4 + 1] = loc_pred[j].ymin();
          loc_pred_data[count * 4 + 2] = loc_pred[j].xmax();
          loc_pred_data[count * 4 + 3] = loc_pred[j].ymax();
        }
        if (encode_variance_in_target) {
          for (int k = 0; k < 4; ++k) {
            CHECK_GT(prior_variances[j][k], 0);
            loc_pred_data[count * 4 + k] /= prior_variances[j][k];
            loc_gt_data[count * 4 + k] /= prior_variances[j][k];
          }
        }
        ++count;
      }
    }
  }
}
