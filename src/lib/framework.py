import datetime as dt
import numpy as np
import os
import random
import glob
import torch
from torch.autograd import Variable
from collections import deque
from lib.define import USE_CUDA, device, load_dump, save_dump, init_logger

from torch.optim import *

from tensorboard_logger import log_value as tblog_value
from tensorboard_logger import configure as tblog_configure
from lib.model import *

class SmapeLoss(torch.nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, predictions, targets, targets_nan):
        predictions = predictions[:, :, :3]
        targets = targets[:, :, :3]
        targets_nan = targets_nan[:, :, :3]
        numerator = torch.abs(predictions - targets) * 200.0
        denominator = torch.abs(predictions) + torch.abs(targets)
        # for kaggle, avoid 0 / 0
        denominator[numerator<1e-2] = 1.0
        targets_not_nan = 1 - targets_nan
        smape = (numerator / denominator) * targets_not_nan
        #avg_smape = smape.sum(dim=1) / targets_not_nan.sum(dim=1)
        avg_smape = smape.sum() / targets_not_nan.sum()
        return avg_smape



class EncDec(object):
    def __init__(self, model_pars):
        self.n_dynamic_features = model_pars['n_dynamic_features']*3
        self.n_fixed_features = model_pars['n_fixed_features']
        self.n_features = self.n_dynamic_features + self.n_fixed_features
        self.n_hidden = model_pars['n_hidden']
        self.n_enc_layers = model_pars['n_enc_layers']
        self.n_dec_layers = model_pars['n_dec_layers']
        self.dropo = model_pars['dropout']
        self.n_out = 6

        if model_pars['enc_file'] is None:
            self.encoder = self.init_encoder()
        else:
            self.load_encoder(model_pars['enc_file'])

        if model_pars['dec_file'] is None:
            self.decoder = self.init_decoder()
        else:
            self.load_decoder(model_pars['dec_file'])

        self.clip = model_pars['clip']
        self.lr = model_pars['lr']
        #self.train_batch_per_epoch = model_pars['train_batch_per_epoch']
        #self.validate_batch_per_epoch = model_pars['validate_batch_per_epoch']
        self.timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        self.model_file = None

        self.n_training_steps = 100000000
        self.loss_averaging_window = 100
        self.log_interval = 10
        self.min_steps_to_checkpoint = 200
        self.early_stopping_steps = 500
        self.lr_scheduler = None
        self.with_weights = False
        self.logger = init_logger(log_file='../logs/{}.log'.format(self.timestamp))

        self.with_tblog = model_pars['with_tblog']
        if self.with_tblog:
            tblog_configure('../tblog/' + self.timestamp)

        self.set_loss_fn(model_pars['loss_type'])
        self.encoder_optimizer = self.set_optimizer(self.encoder, model_pars['encoder']['optimizer'])
        self.decoder_optimizer = self.set_optimizer(self.decoder, model_pars['decoder']['optimizer'])

        if USE_CUDA:
            self.encoder.cuda()
            self.decoder.cuda()

    def tblog_value(self, name, value, step):
        if self.with_tblog:
            tblog_value(name, value, step)

    def enable_train(self, mode=True):
        self.encoder.train(mode)
        self.decoder.train(mode)

    def set_optimizer(self, model, optim_pars):
        if optim_pars['type'] == 'SGD':
            optimizer = SGD(model.parameters(), lr=self.lr, weight_decay=optim_pars['l2_scale'], momentum=optim_pars['momentum'], dampening=optim_pars['dampening'], nesterov=optim_pars['nesterov'])
        elif optim_pars['type'] == 'Adadelta':
            optimizer = Adadelta(model.parameters(), lr=self.lr, rho=optim_pars['rho'], weight_decay=optim_pars['l2_scale'], eps=optim_pars['epsilon'])
        elif optim_pars['type'] == 'Adam':
            optimizer = Adam(model.parameters(), lr=self.lr, betas=(optim_pars['beta1'], optim_pars['beta2']), eps=optim_pars['epsilon'], weight_decay=optim_pars['l2_scale'])
        elif optim_pars['type'] == 'RMSprop':
            optimizer = RMSprop(model.parameters(), lr=self.lr, alpha=optim_pars['rho'], eps=optim_pars['epsilon'], weight_decay=optim_pars['l2_scale'], momentum=optim_pars['momentum'], centered=optim_pars['centered'])
        return optimizer

    def set_loss_fn(self, type='L1Loss'):
        if type == 'L1Loss':
            self.criterion = torch.nn.L1Loss(size_average=False)
        elif type == 'SMAPE':
            self.criterion = SmapeLoss()

    def init_encoder(self):
        self.encoder = EncoderRnn(self.n_features, self.n_hidden, self.n_enc_layers, dropout=self.dropo)
        return self.encoder

    def init_decoder(self):
        self.decoder = DecoderRnn(self.n_hidden, self.n_out, self.n_dec_layers, dropout=self.dropo)
        return self.decoder

    def save_model(self, model_prefix):
        enc_file = model_prefix + '_enc.pth'
        dec_file = model_prefix + '_dec.pth'
        torch.save(self.encoder, enc_file)
        torch.save(self.decoder, dec_file)

    def load_encoder(self, enc_file):
        self.encoder = torch.load(enc_file)

    def load_decoder(self, dec_file):
        self.decoder = torch.load(dec_file)

    def load_models(self, model_files):
        enc_file = model_files[0]
        dec_file = model_files[1]
        self.encoder = torch.load(os.path.join(self.model_dir, enc_file))
        self.decoder = torch.load(os.path.join(self.model_dir, dec_file))

        #if USE_CUDA:
        #    self.encoder.cuda()
        #    self.decoder.cuda()

    def set_train(self, mode=True):
        self.encoder.train(mode)
        self.decoder.train(mode)

    def train_batch(self, input_batches, target_batches):
        input_batches = Variable(input_batches)
        target_batches = Variable(target_batches)

        # Zero gradients of both optimizers
        self.encoder_optimizer.zero_grad()
        self.decoder_optimizer.zero_grad()

        #target_batches = target_batches.float()

        # Run words through encoder
        if USE_CUDA:
            input_batches = input_batches.cuda()

        input_batches = self.transform(input_batches)
        encoder_outputs, encoder_hidden = self.encoder(input_batches, hidden=None)

        decoder_outputs, decoder_hidden = self.decoder(encoder_outputs, encoder_hidden)
        predictions = self.inv_transform(decoder_outputs)

        # Move new Variables to CUDA
        if USE_CUDA:
            target_batches = target_batches.cuda()

        # Loss calculation and backpropagation
        loss = self.criterion(predictions, target_batches)

        loss.backward()

        # Clip gradient norms
        enc_clip = torch.nn.utils.clip_grad_norm(self.encoder.parameters(), self.clip)
        dec_clip = torch.nn.utils.clip_grad_norm(self.decoder.parameters(), self.clip)

        # Update parameters with optimizers
        self.encoder_optimizer.step()
        self.decoder_optimizer.step()

        return loss.data[0], enc_clip, dec_clip


    def train(self, train_bb):
        self.set_train(True)
        epoch_loss = 0
        #train epoch

        tq = tqdm(range(1, self.train_batch_per_epoch+1), unit='batch')
        #for batch_cnt in range(self.train_batch_per_epoch):
        for batch_cnt in tq:
            tq.set_description('Batch %i/%i' % (batch_cnt, self.train_batch_per_epoch))
            #input_seq, _, _, target_seq = self.train_bb.build_batch()
            input_seq, _, _, target_seq = train_bb.build_batch()

            # Run the train function
            batch_loss, enc_clip, dec_clip = self.train_batch(input_seq, target_seq)
            epoch_loss += batch_loss
            tq.set_postfix(train_loss=round(epoch_loss/batch_cnt, 3), enc_clip=round(enc_clip, 4), dec_clip=round(dec_clip, 4))
        epoch_loss /= self.train_batch_per_epoch
        return epoch_loss

    def validate_batch(self, input_batches, target_batches):
        return 0

    def validate(self, validate_bb):
        self.set_train(False)
        epoch_loss = 0
        #validate epoch
        for batch_cnt in range(self.validate_batch_per_epoch):
            #input_seq, _, _, target_seq = self.validate_bb.build_batch()
            input_seq, _, _, target_seq = validate_bb.build_batch()

            batch_loss = self.validate_batch(input_seq, target_seq)
            epoch_loss += batch_loss
        epoch_loss /= self.validate_batch_per_epoch
        return epoch_loss

    def reconfig_model(self, config_file):
        with open(config_file, 'r') as f:
            pars = yaml.safe_load(f)
        active_model(self.encoder)
        self.set_optimizer(self.encoder, pars['encoder']['optimizer'])
        active_model(self.decoder)
        self.set_optimizer(self.decoder, pars['decoder']['optimizer'])

    def run_train(self, train_bb, validate_bb, epochs=10, **kwargs):
        kf = ''
        if 'kf' in kwargs:
            kf = '_kf{}_'.format(kwargs['kf'])
        prefix = 'wtf_' + self.timestamp + kf

        save_freq = 0
        if 'save_freq' in kwargs:
            save_freq = int(kwargs['save_freq'])

        tblg.configure('../output/tblog/{}'.format(self.timestamp), flush_secs=10)

        #tq = tqdm(range(1, epochs + 1), unit='epoch')
        for epoch in range(1, epochs + 1):
            self.reconfig_model(config_file)
            if self.enc_freeze_span[0] <= epoch <= self.enc_freeze_span[1]:
                print('Freeze encoder')
                logging.info('Freeze encoder')
                freeze_model(self.encoder)
            else:
                print('Active encoder')
                logging.info('Active encoder')
                active_model(self.encoder)

            print(dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f"))
            print('************************ Training epoch {} *******************************'.format(epoch))
            logging.info('************************ Training epoch {} *******************************'.format(epoch))
            #tq.set_description('Epoch %i/%i' % (epoch, epochs))
            train_loss = self.train(train_bb)
            tblg.log_value('train_loss', train_loss, epoch)
            logging.info('Training loss: {}'.format(train_loss))
            #print('Epoch {}, training loss: {}'.format(epoch, train_loss[0]))
            validate_score = self.validate(validate_bb)
            tblg.log_value('validate_smape', validate_score, epoch)
            print('Validation Smape score: {}'.format(validate_score))
            logging.info('Validation Smape score: {}'.format(validate_score))
            #tq.set_postfix(train_loss=train_loss, validate_smape=validate_score)

            if save_freq > 0 and epoch % save_freq == 0:
                enc_model_file = prefix + str(epoch) + '_enc.pth'
                dec_model_file = prefix + str(epoch) + '_dec.pth'
                print('Save model to files: {}, {}'.format(enc_model_file, dec_model_file))
                logging.info('Save model to files: {}, {}'.format(enc_model_file, dec_model_file))
                self.save_model(enc_model_file, dec_model_file)

            print('\n\n')
            logging.info('\n\n')

    def fit(self, TrainGen, ValGen, kwargs={}):
        #summary = torch_summarize_df((self.model.n_features, self.model.past_len), self.model)
        #self.logger.info(summary)
        #self.logger.info('total trainable parameters: {}'.format(summary['nb_params'].sum()))
        clf_dir = '../clf/'

        max_score = 1.0
        sb_len = 7
        kf = ''
        if 'kf' in kwargs:
            kf = 'kf{}_'.format(kwargs['kf'])
        prefix = 'kdd_' + kf

        save_freq = 0
        if 'save_freq' in kwargs:
            save_freq = int(kwargs['save_freq'])

        #tblg.configure('../output/tblog/{}'.format(self.timestamp), flush_secs=10)

        train_loss_history = deque(maxlen=self.loss_averaging_window)
        train_accuracy_history = deque(maxlen=self.loss_averaging_window)
        val_loss_history = deque(maxlen=self.loss_averaging_window // self.log_interval)
        val_accuracy_history = deque(maxlen=self.loss_averaging_window)

        step = 0
        scoreboard_file = clf_dir + 'scoreboard.pkl'
        if os.path.isfile(scoreboard_file):
            scoreboard = load_dump(scoreboard_file)
        else:
            scoreboard = []

        last_save_step = 0
        best_val_loss = 200.0
        best_val_loss_step = 0
        best_score = 0.0
        best_score_step = 0
        best_val_accuracy = 0.4
        best_val_accuracy_step = 0
        best_val_f1 = 0.4
        best_val_f1_step = 0

        loss_cnt = 0
        acc_cnt = 0
        f1_cnt = 0
        while step < self.n_training_steps:
            #self.logger.info(step)
            #self.kb_adjust()
            #if self.lr_scheduler and not isinstance(self.lr_scheduler, ReduceLROnPlateau):
            #    self.lr_scheduler.step()
            if self.lr_scheduler:
                self.lr_scheduler.step()

            # train step
            train_batch = next(TrainGen)
            train_fn_loss, enc_clip, dec_clip = self.train_batch(train_batch)

            if step % self.log_interval == 0:
                lr = self.lr
                if self.lr_scheduler:
                    lr = self.lr_scheduler.get_lr()[0]
                self.logger.info('lr = {}'.format(lr))
                self.tblog_value('lr', lr, step)
                # validation evaluation
                if self.with_weights:
                    val_batch, val_target, val_weight = next(ValGen)
                else:
                    val_batch = next(ValGen)
                val_fn_loss = self.validate_batch(val_batch)

                train_loss = train_fn_loss
                train_loss_history.append(train_loss)
                val_loss = val_fn_loss
                val_loss_history.append(val_loss)

                self.logger.info('\n')
                #self.logger.info('accuracy: {}, regularization_loss: {}'.format(accuracy, reg_loss))
                avg_train_loss = sum(train_loss_history) / len(train_loss_history)
                avg_val_loss = sum(val_loss_history) / len(val_loss_history)
                metric_log = (
                    "[step {:6d}]]      "
                    "[[train]]      loss: {:10.3f}     "
                    "[[val]]      loss: {:10.3f}     "
                ).format(step, round(avg_train_loss, 3), round(val_loss, 3))
                #).format(step, round(avg_train_loss, 3), round(avg_val_loss, 3))
                self.logger.info(metric_log)

                self.tblog_value('train_fn_loss', train_loss, step)
                self.tblog_value('val_fn_loss', val_loss, step)

                if step > self.min_steps_to_checkpoint:
                    if val_loss < best_val_loss - 0.0001:
                        best_val_loss = val_loss
                        best_val_loss_step = step
                        self.logger.info('$$$$$$$$$$$$$ Best loss {} at training step {} $$$$$$$$$'.format(best_val_loss, best_val_loss_step))

                        model_prefix = clf_dir + prefix + self.timestamp + '_' + str(step)
                        self.logger.info('save to {}'.format(model_prefix))
                        self.save_model(model_prefix)

                        if len(scoreboard) == 0 or best_val_loss < scoreboard[-1][0]:
                            scoreboard.append([val_loss, step, self.timestamp, kwargs, model_prefix])
                            scoreboard.sort(key=lambda e: e[0], reverse=False)

                            #remove useless files
                            if len(scoreboard) > sb_len:
                                del_file = scoreboard[-1][-1]
                                tmp_file_list = glob.glob(os.path.basename(del_file))
                                for f in tmp_file_list:
                                    if os.path.isfile(f):
                                        os.remove(f)

                            scoreboard = scoreboard[:sb_len]
                            save_dump(scoreboard, scoreboard_file)

                    #early stopping
                    if self.early_stopping_steps >= 0 and step - best_val_loss_step > self.early_stopping_steps:
                        if 'hp_cnt' in kwargs:
                            self.logger.info('$$$$$$$$$$$$$ Hyper Search {} $$$$$$$$$$$$$$$$$$$$$$$'.format(kwargs['hp_cnt']))
                        self.logger.info('early stopping - ending training at {}.'.format(step))
                        break

                    # prevent overfitting
                    #if abs(avg_val_loss - avg_train_loss) / (avg_train_loss + avg_val_loss) > 0.13:
                    #    if 'hp_cnt' in hp_pars:
                    #        self.logger.info('$$$$$$$$$$$$$ Hyper Search {} $$$$$$$$$$$$$$$$$$$$$$$'.format(hp_pars['hp_cnt']))
                    #    self.logger.info('found overfitting at {}, val_loss {}, train_loss {}'.format(step, avg_val_loss, avg_train_loss))
                    #    break
            step += 1

        self.logger.info('best validation loss of {} at training step {}'.format(best_val_loss, best_val_loss_step))
        return best_val_loss


    def predict_batch(self, input_batches, predict_seq_len):
        return 0

    def predict(self, predict_bb, predict_seq_len):
        self.set_train(False)

        predict_results = []
        batch_cnt = 0
        for batch in predict_bb:
            batch_cnt += 1
            if batch_cnt % 100 == 0:
                print('Predicted %d batchs' % (batch_cnt))
            #print(batch_data.size())
            pred_batch = self.predict_batch(batch, predict_seq_len)
            predict_results.append(pred_batch.cpu().data.numpy())

        #predict_results = torch.cat(predict_results)
        #predict_results = predict_results.cpu().data.numpy()
        predict_results = np.concatenate(predict_results)
        #predict_results = predict_results.clip(0)
        return predict_results


class Seq2Seq(EncDec):
    def __init__(self, model_pars):
        super().__init__(model_pars)

        self.teacher_forcing_ratio = model_pars['teacher_forcing_ratio']

    def transform(self, x):
        self.x_mean = torch.mean(x, dim=1, keepdim=True)
        x_trans = x - self.x_mean
        x_mean = self.x_mean.repeat((1, x.shape[1], 1))
        return x_trans, x_mean

    def inv_transform(self, x):
        return x + self.x_mean

    def train_batch(self, batch):
        self.enable_train(True)
        #x_encode = batch['x_encode']
        #encode_len = batch['encode_len']
        #y_decode = batch['y_decode']
        #decode_len = batch['decode_len']
        #is_nan_encode = batch['is_nan_encode']
        #is_nan_decode = batch['is_nan_decode']
        with torch.set_grad_enabled(True):
            y_decode = Variable(torch.from_numpy(batch['y_decode'])).to(device)
            y_decode.requires_grad_()
            enc_dynamic = Variable(torch.from_numpy(batch['enc_dynamic'])).to(device)
            enc_dynamic.requires_grad_()
            enc_fixed = Variable(torch.from_numpy(batch['enc_fixed'])).to(device)
            enc_fixed.requires_grad_()
            enc_dynamic_nan = Variable(torch.from_numpy(batch['enc_dynamic_nan'])).to(device)
            enc_dynamic_nan.requires_grad_()
            is_nan_decode = Variable(torch.from_numpy(batch['is_nan_decode'])).to(device)
            is_nan_decode.requires_grad_()
            enc_dynamic_trans, enc_dynamic_mean = self.transform(enc_dynamic)
            data_batch = torch.cat([enc_fixed, enc_dynamic_trans, enc_dynamic_nan, enc_dynamic_mean], dim=2)

            encoder_outputs, encoder_hidden = self.encoder(data_batch, None)

            # Prepare input and output variables
            decoder_input = encoder_outputs[:, -1, :].unsqueeze(1)
            decoder_hidden = encoder_hidden[:self.n_dec_layers, :, :] # Use last (forward) hidden state from encoder

            target_len = y_decode.shape[1]
            batch_size = enc_dynamic.shape[0]
            all_decoder_outputs = torch.zeros(target_len, batch_size, self.n_out, requires_grad=True)

            all_decoder_outputs = all_decoder_outputs.to(device)
            target_batches = y_decode.to(device)

            use_teacher_forcing = True if random.random() < self.teacher_forcing_ratio else False
            for t in range(target_len):
                #decoder_output, decoder_hidden, decoder_attn = self.decoder(decoder_input, decoder_hidden, encoder_outputs)
                decoder_output, decoder_hidden = self.decoder(decoder_input, decoder_hidden)

                #print(all_decoder_outputs[t].size(), decoder_output[0].size())
                all_decoder_outputs[t] = decoder_output[0]
                if use_teacher_forcing:
                    decoder_input = target_batches[:, -1, :].view(batch_size, 1, -1)
                else:
                    decoder_input = decoder_output      # Next input is current prediction

            # Loss calculation and backpropagation
            predictions = all_decoder_outputs.permute(1, 0, 2)
            predictions = self.inv_transform(predictions)
            loss = self.criterion(predictions, target_batches, is_nan_decode)

            # Zero gradients of both optimizers
            self.encoder_optimizer.zero_grad()
            self.decoder_optimizer.zero_grad()

            loss.backward()
            #for param in self.decoder.parameters():
            #    print(param.grad.data.sum())

            # Clip gradient norms
            enc_clip = torch.nn.utils.clip_grad_norm(self.encoder.parameters(), self.clip)
            dec_clip = torch.nn.utils.clip_grad_norm(self.decoder.parameters(), self.clip)

            # Update parameters with optimizers
            self.encoder_optimizer.step()
            self.decoder_optimizer.step()
            return loss.item(), enc_clip, dec_clip

    def validate_batch(self, batch):
        self.enable_train(False)
        with torch.no_grad():
            y_decode = (torch.from_numpy(batch['y_decode'])).to(device)
            enc_dynamic = (torch.from_numpy(batch['enc_dynamic'])).to(device)
            enc_fixed = (torch.from_numpy(batch['enc_fixed'])).to(device)
            enc_dynamic_nan = (torch.from_numpy(batch['enc_dynamic_nan'])).to(device)
            is_nan_decode = (torch.from_numpy(batch['is_nan_decode'])).to(device)
            enc_dynamic_trans, enc_dynamic_mean = self.transform(enc_dynamic)
            data_batch = torch.cat([enc_fixed, enc_dynamic_trans, enc_dynamic_nan, enc_dynamic_mean], dim=2)

            encoder_outputs, encoder_hidden = self.encoder(data_batch, None)

            # Prepare input and output variables
            decoder_input = encoder_outputs[:, -1, :].unsqueeze(1)
            decoder_hidden = encoder_hidden[:self.n_dec_layers, :, :] # Use last (forward) hidden state from encoder

            target_len = y_decode.shape[1]
            batch_size = enc_dynamic.shape[0]
            all_decoder_outputs = (torch.zeros(target_len, batch_size, self.n_out))

            all_decoder_outputs = all_decoder_outputs.to(device)
            target_batches = y_decode.to(device)

            for t in range(target_len):
                #decoder_output, decoder_hidden, decoder_attn = self.decoder(decoder_input, decoder_hidden, encoder_outputs)
                decoder_output, decoder_hidden = self.decoder(decoder_input, decoder_hidden)

                #print(all_decoder_outputs[t].size(), decoder_output[0].size())
                all_decoder_outputs[t] = decoder_output[0]
                decoder_input = decoder_output      # Next input is current prediction

            # Loss calculation and backpropagation
            predictions = all_decoder_outputs.permute(1, 0, 2)
            predictions = self.inv_transform(predictions)
            loss = self.criterion(predictions, target_batches, is_nan_decode)
            return loss.item()

    def predict_batch(self, batch, predict_seq_len):
        self.enable_train(False)
        with torch.no_grad():
            y_decode = (torch.from_numpy(batch['y_decode'])).to(device)
            enc_dynamic = (torch.from_numpy(batch['enc_dynamic'])).to(device)
            enc_fixed = (torch.from_numpy(batch['enc_fixed'])).to(device)
            enc_dynamic_nan = (torch.from_numpy(batch['enc_dynamic_nan'])).to(device)
            is_nan_decode = (torch.from_numpy(batch['is_nan_decode'])).to(device)
            enc_dynamic_trans, enc_dynamic_mean = self.transform(enc_dynamic)
            data_batch = torch.cat([enc_fixed, enc_dynamic_trans, enc_dynamic_nan, enc_dynamic_mean], dim=2)

            encoder_outputs, encoder_hidden = self.encoder(data_batch, None)

            # Prepare input and output variables
            decoder_input = encoder_outputs[:, -1, :].unsqueeze(1)
            decoder_hidden = encoder_hidden[:self.n_dec_layers, :, :] # Use last (forward) hidden state from encoder

            batch_size = enc_dynamic.shape[0]
            all_decoder_outputs = (torch.zeros(predict_seq_len, batch_size, self.n_out))

            all_decoder_outputs = all_decoder_outputs.to(device)
            target_batches = y_decode.to(device)

            for t in range(predict_seq_len):
                #decoder_output, decoder_hidden, decoder_attn = self.decoder(decoder_input, decoder_hidden, encoder_outputs)
                decoder_output, decoder_hidden = self.decoder(decoder_input, decoder_hidden)

                #print(all_decoder_outputs[t].size(), decoder_output[0].size())
                all_decoder_outputs[t] = decoder_output[0]
                decoder_input = decoder_output      # Next input is current prediction

            # Loss calculation and backpropagation
            predictions = all_decoder_outputs.permute(1, 0, 2)
            predictions = self.inv_transform(predictions)
            return predictions

    def predict(self, predict_bb, predict_seq_len):
        predict_results = super().predict(predict_bb, predict_seq_len)
        return predict_results.clip(0)

    '''
    def predict_batch(self, input_batches, predict_seq_len):
        input_batches = Variable(input_batches, volatile=True)
        if USE_CUDA:
            input_batches = input_batches.cuda()

        #input_batches = self.transform(input_batches)
        input_batches[:, :, 0] = self.transform(input_batches[:, :, 0].unsqueeze(2))
        encoder_outputs, encoder_hidden = self.encoder(input_batches, hidden=None)

        # Prepare input and output variables
        #decoder_input = Variable(torch.FloatTensor([SOS_token] * self.batch_size).view(1, -1, 1))
        decoder_input = encoder_outputs[-1].unsqueeze(0)
        #decoder_hidden = encoder_hidden[:self.decoder.n_layers].squeeze(0) # Use last (forward) hidden state from encoder
        decoder_hidden = encoder_hidden[:self.decoder.n_layers*self.decoder.num_direction] # Use last (forward) hidden state from encoder

        batch_size = input_batches.size(1)
        all_decoder_outputs = Variable(torch.zeros(predict_seq_len, batch_size, self.decoder.output_size), volatile=True)

        # Move new Variables to CUDA
        if USE_CUDA:
            all_decoder_outputs = all_decoder_outputs.cuda()

        # Run through decoder one time step at a time
        for t in range(predict_seq_len):
            #decoder_output, decoder_hidden, decoder_attn = self.decoder(decoder_input, decoder_hidden, encoder_outputs)
            if self.keep_hidden:
                decoder_output, _ = self.decoder(decoder_input, decoder_hidden)
            else:
                decoder_output, decoder_hidden = self.decoder(decoder_input, decoder_hidden)
            #print(all_decoder_outputs[t].size(), decoder_output[0].size())
            all_decoder_outputs[t] = decoder_output[0]
            #decoder_input = target_batches[t].view(1, -1, 1) # Next input is current target
            decoder_input = decoder_output

        predictions = all_decoder_outputs.squeeze(2)
        predictions = self.inv_transform(predictions).permute(1, 0)
        return predictions
    '''


