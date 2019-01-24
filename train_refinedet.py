import os
import time
import argparse
import torch
from torch.autograd import Variable
import torch.optim as optim
import torch.backends.cudnn as cudnn
import torch.utils.data as data
from libs.utils.augmentations import SSDAugmentation
from libs.networks.vgg_refinedet import VGGRefineDet
from libs.networks.resnet_refinedet import ResNetRefineDet
from libs.dataset.config import voc320, voc512, coco320, coco512, MEANS
from libs.dataset.transform import detection_collate
from libs.dataset.roidb import combined_roidb
from libs.dataset.blob_dataset import BlobDataset

import pdb

# os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['CUDA_VISIBLE_DEVICES'] = '0,1,2'


def str2bool(v):
    return v.lower() in ('yes', 'true', 't', '1')


parser = argparse.ArgumentParser(
    description='RefineDet Training With Pytorch')
parser.add_argument('--dataset', default='pascal_voc_0712',
                    choices=['pascal_voc', 'pascal_voc_0712', 'coco'],
                    type=str, help='pascal_voc, pascal_voc_0712 or coco')
parser.add_argument('--network', default='vgg16',
                    help='Pretrained base model')
parser.add_argument('--basenet', default='vgg16_reducedfc.pth',
                    help='Pretrained base model')
parser.add_argument('--input_size', default=320, type=int,
                    help='Input size for training')
parser.add_argument('--batch_size', default=32, type=int,
                    help='Batch size for training')
parser.add_argument('--resume_checkpoint', default=None, type=str,
                    help='Checkpoint state_dict file to resume training from')
parser.add_argument('--start_iter', default=0, type=int,
                    help='Resume training at this iter')
parser.add_argument('--num_workers', default=8, type=int,
                    help='Number of workers used in dataloading')
parser.add_argument('--cuda', default=True, type=str2bool,
                    help='Use CUDA to train model')
parser.add_argument('--lr', '--learning-rate', default=1e-3, type=float,
                    help='initial learning rate')
parser.add_argument('--momentum', default=0.9, type=float,
                    help='Momentum value for optim')
parser.add_argument('--weight_decay', default=5e-4, type=float,
                    help='Weight decay for SGD')
parser.add_argument('--gamma', default=0.1, type=float,
                    help='Gamma update for SGD')
parser.add_argument('--visdom', default=False, type=str2bool,
                    help='Use visdom for loss visualization')
parser.add_argument('--save_folder', default='weights/vgg16',
                    help='Directory for saving checkpoint models')
args = parser.parse_args()

num_gpus = 1
if torch.cuda.is_available():
    print('CUDA devices: ', torch.cuda.device)
    print('GPU numbers: ', torch.cuda.device_count())
    num_gpus = torch.cuda.device_count()
    
if torch.cuda.is_available():
    if args.cuda:
        torch.set_default_tensor_type('torch.cuda.FloatTensor')
    if not args.cuda:
        print('WARNING: It looks like you have a CUDA device, but are not' +
              'using CUDA.\nRun with --cuda for optimal training speed.')
        torch.set_default_tensor_type('torch.FloatTensor')
else:
    torch.set_default_tensor_type('torch.FloatTensor')

if not os.path.exists(args.save_folder):
    os.mkdir(args.save_folder)

viz = None
if args.visdom:
    import visdom
    viz = visdom.Visdom()
    
def train():
    # Assign imdb_name and imdbval_name according to args.dataset.
    if args.dataset == "pascal_voc":
        args.imdb_name = "voc_2007_trainval"
        args.imdbval_name = "voc_2007_test"
    elif args.dataset == "pascal_voc_0712":
        args.imdb_name = "voc_2007_trainval+voc_2012_trainval"
        args.imdbval_name = "voc_2007_test"
    elif args.dataset == "coco":
        args.imdb_name = "coco_2014_train+coco_2014_valminusminival"
        args.imdbval_name = "coco_2014_minival"
    # Import config
    if args.dataset == 'coco':
        cfg = (coco320, coco512)[args.input_size==512]
    elif args.dataset in ['pascal_voc', 'pascal_voc_0712']:
        cfg = (voc320, voc512)[args.input_size==512]
    # Create imdb, roidb and blob_dataset
    print('Create or load an imdb.')
    imdb, roidb = combined_roidb(args.imdb_name)
    blob_dataset = BlobDataset(
        imdb, roidb, transform=SSDAugmentation(cfg['min_dim'], MEANS),
        target_normalization=True)

    # Construct networks.
    print('Construct {}_refinedet network.'.format(args.network))
    if args.network == 'vgg16':
        refinedet = VGGRefineDet(cfg['num_classes'], cfg)
    elif args.network == 'resnet101':
        refinedet = ResNetRefineDet(cfg['num_classes'], cfg)
    refinedet.create_architecture(
        os.path.join(args.save_folder, args.basenet), pretrained=True,
        fine_tuning=True)
    # For CPU
    net = refinedet
    # For GPU/GPUs
    if args.cuda:
        if num_gpus > 1:
            net = torch.nn.DataParallel(refinedet)
        else:
            net = refinedet.cuda()
        cudnn.benchmark = True
    # Resume
    if args.resume_checkpoint:
        print('Resuming training, loading {}...'.format(args.resume_checkpoint))
        net.load_weights(args.resume_checkpoint)

    # pdb.set_trace()
    # params = net.state_dict()
    # for k, v in params.items():
    #     print(k)
    #     print(v.shape)
    optimizer = optim.SGD(filter(lambda p: p.requires_grad, net.parameters()),
                          lr=args.lr, momentum=args.momentum,
                          weight_decay=args.weight_decay)
    net.train()
    print('Training RefineDet on:', args.imdb_name)
    print('Using the specified args:')
    print(args)

    step_index = 0
    str_input_size = str(cfg['min_dim'])
    
    if args.visdom:
        vis_title = 'RefinDet.PyTorch on ' + args.imdb_name
        vis_legend = ['Binary Loc Loss', 'Binary Conf Loss',
                      'Binary Total Loss',
                      'Multiclass Loc Loss', 'Multiclass Conf Loss',
                      'Multiclass Total Loss',
                      'Total Loss']
        
        iter_plot = create_vis_plot('Iteration', 'Loss', vis_title, vis_legend)
        epoch_plot = create_vis_plot('Epoch', 'Loss', vis_title, vis_legend)

    data_loader = data.DataLoader(blob_dataset, args.batch_size,
                                  num_workers=args.num_workers,
                                  shuffle=True, collate_fn=detection_collate,
                                  pin_memory=True)
    # Create batch iterator
    # Number of iterations in each epoch
    num_iter_per_epoch = len(blob_dataset) // args.batch_size
    # number of epoch
    num_epoch = cfg['max_iter'] // num_iter_per_epoch
    iteration = 0
    bi_loc_loss = 0
    bi_conf_loss = 0
    multi_loc_loss = 0
    multi_conf_loss = 0
    total_bi_loc_loss = 0
    total_bi_conf_loss = 0
    total_multi_loc_loss = 0
    total_multi_conf_loss = 0
    for epoch in range(0, num_epoch):
        if args.visdom and epoch != 0:
            update_vis_plot(epoch, bi_loc_loss, bi_conf_loss,
                            multi_loc_loss, multi_conf_loss, epoch_plot, None,
                            'append', num_iter_per_epoch)
            # reset epoch loss counters
            bi_loc_loss = 0
            bi_conf_loss = 0
            multi_loc_loss = 0
            multi_conf_loss = 0
        
        # pdb.set_trace()
        for i_batch, (images, targets) in enumerate(data_loader):
            if iteration in cfg['lr_steps']:
                step_index += 1
                adjust_learning_rate(optimizer, args.gamma, step_index)
    
            if args.cuda:
                images = Variable(images.cuda())
                targets = Variable(targets.cuda())
            else:
                images = Variable(images)
                targets = Variable(targets)
            # forward
            t0 = time.time()
            # backprop
            optimizer.zero_grad()
            bi_loss_loc, bi_loss_conf, multi_loss_loc, multi_loss_conf = \
                net(images, targets)
            loss = bi_loss_loc.mean() + bi_loss_conf.mean() + \
                   multi_loss_loc.mean() + multi_loss_conf.mean()
            loss.backward()
            optimizer.step()
            t1 = time.time()
            if num_gpus > 1:
                total_bi_loc_loss += bi_loss_loc.mean().data[0]
                total_bi_conf_loss += bi_loss_conf.mean().data[0]
                total_multi_loc_loss += multi_loss_loc.mean().data[0]
                total_multi_conf_loss += multi_loss_conf.mean().data[0]
            else:
                total_bi_loc_loss += bi_loss_loc.data[0]
                total_bi_conf_loss += bi_loss_conf.data[0]
                total_multi_loc_loss += multi_loss_loc.data[0]
                total_multi_conf_loss += multi_loss_conf.data[0]
            
            if iteration % 10 == 0:
                print('timer: %.4f sec.' % (t1 - t0))
                print('iter ' + repr(iteration) +
                      ' || Loss: %.4f ||' % (loss.data[0]) + ' ')
                # print('iter ' + repr(iteration) +
                #       ' || Loss: %.4f ||' % (loss.data[0]), end=' ')
    
            if args.visdom:
                update_vis_plot(
                    iteration, bi_loss_loc.data[0], bi_loss_conf.data[0],
                    multi_loss_loc.data[0], multi_loss_conf.data[0],
                    iter_plot, epoch_plot, 'append')
    
            if iteration != 0 and iteration % cfg['checkpoint_step'] == 0:
                print('Saving state, iter:', iteration)
                torch.save(refinedet.state_dict(),
                           os.path.join(args.save_folder,
                           'refinedet{0}_'.format(str_input_size) +
                           args.dataset + '_' +
                           repr(iteration) + '.pth'))

            iteration += 1
        
    torch.save(refinedet.state_dict(),
               os.path.join(args.save_folder, args.dataset + '.pth'))
            
            


def adjust_learning_rate(optimizer, gamma, step):
    """Sets the learning rate to the initial LR decayed by 10 at every
        specified step
    # Adapted from PyTorch Imagenet example:
    # https://github.com/pytorch/examples/blob/master/imagenet/main.py
    """
    lr = args.lr * (gamma ** (step))
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr




def create_vis_plot(_xlabel, _ylabel, _title, _legend):
    return viz.line(
        X=torch.zeros((1,)).cpu(),
        Y=torch.zeros((1, len(_legend))).cpu(),
        opts=dict(
            xlabel=_xlabel,
            ylabel=_ylabel,
            title=_title,
            legend=_legend
        )
    )


def update_vis_plot(iteration, bi_loc, bi_conf, multi_loc, multi_conf,
                    window1, window2, update_type, num_iter_per_epoch=1):
    num_loss_type = 6
    viz.line(
        X=torch.ones((1, num_loss_type)).cpu() * iteration,
        Y=torch.Tensor([bi_loc, bi_conf, bi_loc + bi_conf,
                        multi_loc, multi_conf, multi_loc + multi_conf,
                        bi_loc + bi_conf + multi_loc + multi_conf]
                       ).unsqueeze(0).cpu() / num_iter_per_epoch,
        win=window1,
        update=update_type
    )
    # initialize epoch plot on first iteration
    if iteration == 0:
        viz.line(
            X=torch.zeros((1, num_loss_type)).cpu(),
            Y=torch.Tensor([bi_loc, bi_conf, bi_loc + bi_conf,
                        multi_loc, multi_conf, multi_loc + multi_conf,
                        bi_loc + bi_conf + multi_loc + multi_conf]).unsqueeze(0).cpu(),
            win=window2,
            update=True
        )


if __name__ == '__main__':
    train()
